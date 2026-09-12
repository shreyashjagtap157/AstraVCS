use std::fmt;

pub const MAGIC: &[u8; 6] = b"ASTRA\0";
pub const CODEC_VERSION: u16 = 0;
pub const MAX_PAYLOAD_BYTES: usize = 64 * 1024 * 1024;
const HEADER_BYTES: usize = 6 + 1 + 2 + 8;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(u8)]
pub enum ObjectType {
    Content = 1,
    Tree = 2,
    ChangeVersion = 3,
    Revision = 4,
    View = 5,
    Operation = 6,
    Conflict = 7,
    Attestation = 8,
    ReleaseManifest = 9,
}

impl TryFrom<u8> for ObjectType {
    type Error = CodecError;

    fn try_from(value: u8) -> Result<Self, Self::Error> {
        match value {
            1 => Ok(Self::Content),
            2 => Ok(Self::Tree),
            3 => Ok(Self::ChangeVersion),
            4 => Ok(Self::Revision),
            5 => Ok(Self::View),
            6 => Ok(Self::Operation),
            7 => Ok(Self::Conflict),
            8 => Ok(Self::Attestation),
            9 => Ok(Self::ReleaseManifest),
            _ => Err(CodecError::UnknownObjectType(value)),
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum CodecError {
    TruncatedHeader,
    InvalidMagic,
    UnknownObjectType(u8),
    UnsupportedVersion(u16),
    PayloadTooLarge(u64),
    TruncatedPayload,
    TrailingBytes,
}

impl fmt::Display for CodecError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::TruncatedHeader => write!(f, "truncated bootstrap object header"),
            Self::InvalidMagic => write!(f, "invalid bootstrap object magic"),
            Self::UnknownObjectType(value) => write!(f, "unknown bootstrap object type: {value}"),
            Self::UnsupportedVersion(version) => {
                write!(f, "unsupported bootstrap codec version: {version}")
            }
            Self::PayloadTooLarge(size) => {
                write!(f, "payload exceeds bootstrap codec size limit: {size}")
            }
            Self::TruncatedPayload => write!(f, "truncated bootstrap object payload"),
            Self::TrailingBytes => write!(f, "trailing bytes after bootstrap object payload"),
        }
    }
}

impl std::error::Error for CodecError {}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ObjectEnvelope {
    pub object_type: ObjectType,
    pub payload: Vec<u8>,
    pub version: u16,
}

impl ObjectEnvelope {
    pub fn new(object_type: ObjectType, payload: Vec<u8>) -> Self {
        Self {
            object_type,
            payload,
            version: CODEC_VERSION,
        }
    }

    pub fn encode(&self) -> Result<Vec<u8>, CodecError> {
        if self.version != CODEC_VERSION {
            return Err(CodecError::UnsupportedVersion(self.version));
        }
        if self.payload.len() > MAX_PAYLOAD_BYTES {
            return Err(CodecError::PayloadTooLarge(self.payload.len() as u64));
        }
        let mut out = Vec::with_capacity(HEADER_BYTES + self.payload.len());
        out.extend_from_slice(MAGIC);
        out.push(self.object_type as u8);
        out.extend_from_slice(&self.version.to_be_bytes());
        out.extend_from_slice(&(self.payload.len() as u64).to_be_bytes());
        out.extend_from_slice(&self.payload);
        Ok(out)
    }

    pub fn decode(data: &[u8]) -> Result<Self, CodecError> {
        if data.len() < HEADER_BYTES {
            return Err(CodecError::TruncatedHeader);
        }
        if &data[..MAGIC.len()] != MAGIC {
            return Err(CodecError::InvalidMagic);
        }
        let object_type = ObjectType::try_from(data[MAGIC.len()])?;
        let version_start = MAGIC.len() + 1;
        let version = u16::from_be_bytes(
            data[version_start..version_start + 2]
                .try_into()
                .map_err(|_| CodecError::TruncatedHeader)?,
        );
        if version != CODEC_VERSION {
            return Err(CodecError::UnsupportedVersion(version));
        }
        let length_start = version_start + 2;
        let payload_len = u64::from_be_bytes(
            data[length_start..length_start + 8]
                .try_into()
                .map_err(|_| CodecError::TruncatedHeader)?,
        );
        if payload_len > MAX_PAYLOAD_BYTES as u64 {
            return Err(CodecError::PayloadTooLarge(payload_len));
        }
        let payload_len = payload_len as usize;
        let expected = HEADER_BYTES + payload_len;
        if data.len() < expected {
            return Err(CodecError::TruncatedPayload);
        }
        if data.len() > expected {
            return Err(CodecError::TrailingBytes);
        }
        Ok(Self {
            object_type,
            payload: data[HEADER_BYTES..].to_vec(),
            version,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_trip_is_exact() {
        let envelope = ObjectEnvelope::new(ObjectType::Tree, b"payload".to_vec());
        let encoded = envelope.encode().unwrap();
        assert_eq!(ObjectEnvelope::decode(&encoded).unwrap(), envelope);
        assert_eq!(ObjectEnvelope::decode(&encoded).unwrap().encode().unwrap(), encoded);
    }

    fn expected_vector(name: &str) -> &'static str {
        include_str!("../../../tests/vectors/codec-v0.tsv")
            .lines()
            .filter(|line| !line.is_empty() && !line.starts_with('#'))
            .find_map(|line| {
                let (key, value) = line.split_once('\t')?;
                (key == name).then_some(value)
            })
            .unwrap_or_else(|| panic!("missing codec vector: {name}"))
    }

    fn hex(bytes: &[u8]) -> String {
        bytes.iter().map(|byte| format!("{byte:02x}")).collect()
    }

    #[test]
    fn bootstrap_codec_vectors_match() {
        assert_eq!(
            hex(&ObjectEnvelope::new(ObjectType::Content, vec![]).encode().unwrap()),
            expected_vector("content.empty")
        );
        assert_eq!(
            hex(&ObjectEnvelope::new(ObjectType::Tree, b"payload".to_vec()).encode().unwrap()),
            expected_vector("tree.payload")
        );
        assert_eq!(
            hex(&ObjectEnvelope::new(ObjectType::Revision, (0_u8..16).collect()).encode().unwrap()),
            expected_vector("revision.binary")
        );
        assert_eq!(
            hex(&ObjectEnvelope::new(ObjectType::Conflict, b"rename/rename".to_vec()).encode().unwrap()),
            expected_vector("conflict.text")
        );
    }

    #[test]
    fn rejects_malformed_envelopes() {
        assert_eq!(ObjectEnvelope::decode(MAGIC), Err(CodecError::TruncatedHeader));
        let mut unknown = ObjectEnvelope::new(ObjectType::Content, vec![]).encode().unwrap();
        unknown[MAGIC.len()] = 255;
        assert_eq!(ObjectEnvelope::decode(&unknown), Err(CodecError::UnknownObjectType(255)));
        let mut trailing = ObjectEnvelope::new(ObjectType::Content, b"x".to_vec()).encode().unwrap();
        trailing.push(0);
        assert_eq!(ObjectEnvelope::decode(&trailing), Err(CodecError::TrailingBytes));
    }
}
