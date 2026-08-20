use sha2::{Digest, Sha256};
use std::fmt;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Clone, Copy, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub struct ObjectId(pub [u8; 32]);

impl ObjectId {
    pub fn digest(domain: &[u8], parts: &[&[u8]]) -> Self {
        let mut hasher = Sha256::new();
        hasher.update((domain.len() as u64).to_be_bytes());
        hasher.update(domain);
        for part in parts {
            hasher.update((part.len() as u64).to_be_bytes());
            hasher.update(part);
        }
        Self(hasher.finalize().into())
    }

    pub fn to_hex(self) -> String {
        self.0.iter().map(|b| format!("{b:02x}")).collect()
    }
}

impl fmt::Display for ObjectId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        for byte in self.0 {
            write!(f, "{byte:02x}")?;
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub struct ContentId(pub ObjectId);

impl ContentId {
    pub fn from_bytes(bytes: &[u8]) -> Self {
        Self(ObjectId::digest(b"ASTRA:CONTENT:V0", &[bytes]))
    }
}

#[derive(Clone, Copy, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub struct NodeId(pub [u8; 16]);

#[derive(Clone, Copy, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub struct ChangeId(pub [u8; 16]);

static LOGICAL_ID_COUNTER: AtomicU64 = AtomicU64::new(0);

fn bootstrap_logical_id(domain: &[u8]) -> [u8; 16] {
    // Bootstrap-only generator: combines process-local monotonic state and
    // high-resolution wall time before hashing. Production must replace this
    // with an OS CSPRNG-backed generator before stable-format freeze.
    let counter = LOGICAL_ID_COUNTER.fetch_add(1, Ordering::Relaxed);
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos()
        .to_be_bytes();
    let digest = ObjectId::digest(domain, &[&now, &counter.to_be_bytes()]);
    let mut out = [0_u8; 16];
    out.copy_from_slice(&digest.0[..16]);
    out
}

impl NodeId {
    pub fn bootstrap_new() -> Self {
        Self(bootstrap_logical_id(b"ASTRA:NODE-ID:BOOTSTRAP"))
    }
}

impl ChangeId {
    pub fn bootstrap_new() -> Self {
        Self(bootstrap_logical_id(b"ASTRA:CHANGE-ID:BOOTSTRAP"))
    }
}
