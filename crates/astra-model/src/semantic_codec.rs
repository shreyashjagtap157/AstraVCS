use crate::{
    ChangeId, ChangeVersion, Conflict, ContentId, NodeEntry, NodeId, NodeKind, ObjectEnvelope,
    ObjectId, ObjectType, Operation, RepositoryView, Revision, Tree, ValidationError,
};
use std::collections::BTreeMap;
use std::fmt;

pub const MAX_COLLECTION_ITEMS: u32 = 1_000_000;

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum SemanticObject {
    Content(Vec<u8>),
    Tree(Tree),
    ChangeVersion(ChangeVersion),
    Revision(Revision),
    View(RepositoryView),
    Operation(Operation),
    Conflict(Conflict),
    Attestation(Attestation),
    ReleaseManifest(ReleaseManifest),
}

impl SemanticObject {
    pub fn object_type(&self) -> ObjectType {
        match self {
            Self::Content(_) => ObjectType::Content,
            Self::Tree(_) => ObjectType::Tree,
            Self::ChangeVersion(_) => ObjectType::ChangeVersion,
            Self::Revision(_) => ObjectType::Revision,
            Self::View(_) => ObjectType::View,
            Self::Operation(_) => ObjectType::Operation,
            Self::Conflict(_) => ObjectType::Conflict,
            Self::Attestation(_) => ObjectType::Attestation,
            Self::ReleaseManifest(_) => ObjectType::ReleaseManifest,
        }
    }

    pub fn semantic_id(&self) -> ObjectId {
        match self {
            Self::Content(bytes) => (ContentId::from_bytes(bytes)).0,
            Self::Tree(value) => value.id(),
            Self::ChangeVersion(value) => value.id(),
            Self::Revision(value) => value.id(),
            Self::View(value) => value.id(),
            Self::Operation(value) => value.id(),
            Self::Conflict(value) => value.id(),
            Self::Attestation(value) => value.semantic_id(),
            Self::ReleaseManifest(value) => value.semantic_id(),
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum SemanticCodecError {
    Truncated,
    TrailingBytes,
    CountTooLarge,
    BlobTooLarge,
    UnknownNodeKind(u8),
    InvalidOptionalMarker(u8),
    NonCanonicalOrder(&'static str),
    DuplicatePath,
    Validation(ValidationError),
    ObjectTypeMismatch,
    NonCanonical,
}

impl fmt::Display for SemanticCodecError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{self:?}")
    }
}

impl std::error::Error for SemanticCodecError {}

impl From<ValidationError> for SemanticCodecError {
    fn from(value: ValidationError) -> Self {
        Self::Validation(value)
    }
}

struct Reader<'a> {
    data: &'a [u8],
    offset: usize,
}

impl<'a> Reader<'a> {
    fn new(data: &'a [u8]) -> Self {
        Self { data, offset: 0 }
    }

    fn take(&mut self, size: usize) -> Result<&'a [u8], SemanticCodecError> {
        let end = self.offset.checked_add(size).ok_or(SemanticCodecError::Truncated)?;
        if end > self.data.len() {
            return Err(SemanticCodecError::Truncated);
        }
        let out = &self.data[self.offset..end];
        self.offset = end;
        Ok(out)
    }

    fn u8(&mut self) -> Result<u8, SemanticCodecError> {
        Ok(self.take(1)?[0])
    }

    fn u32(&mut self) -> Result<u32, SemanticCodecError> {
        Ok(u32::from_be_bytes(self.take(4)?.try_into().map_err(|_| SemanticCodecError::Truncated)?))
    }

    fn count(&mut self) -> Result<u32, SemanticCodecError> {
        let value = self.u32()?;
        if value > MAX_COLLECTION_ITEMS {
            return Err(SemanticCodecError::CountTooLarge);
        }
        Ok(value)
    }

    fn u64(&mut self) -> Result<u64, SemanticCodecError> {
        Ok(u64::from_be_bytes(self.take(8)?.try_into().map_err(|_| SemanticCodecError::Truncated)?))
    }

    fn blob(&mut self) -> Result<Vec<u8>, SemanticCodecError> {
        let len = usize::try_from(self.u64()?).map_err(|_| SemanticCodecError::BlobTooLarge)?;
        Ok(self.take(len)?.to_vec())
    }

    fn object_id(&mut self) -> Result<ObjectId, SemanticCodecError> {
        let mut bytes = [0_u8; 32];
        bytes.copy_from_slice(self.take(32)?);
        Ok(ObjectId(bytes))
    }

    fn node_id(&mut self) -> Result<NodeId, SemanticCodecError> {
        let mut bytes = [0_u8; 16];
        bytes.copy_from_slice(self.take(16)?);
        Ok(NodeId(bytes))
    }

    fn change_id(&mut self) -> Result<ChangeId, SemanticCodecError> {
        let mut bytes = [0_u8; 16];
        bytes.copy_from_slice(self.take(16)?);
        Ok(ChangeId(bytes))
    }

    fn finish(self) -> Result<(), SemanticCodecError> {
        if self.offset == self.data.len() {
            Ok(())
        } else {
            Err(SemanticCodecError::TrailingBytes)
        }
    }
}

fn push_blob(out: &mut Vec<u8>, bytes: &[u8]) {
    out.extend_from_slice(&(bytes.len() as u64).to_be_bytes());
    out.extend_from_slice(bytes);
}

fn push_count(out: &mut Vec<u8>, count: usize) -> Result<(), SemanticCodecError> {
    let count = u32::try_from(count).map_err(|_| SemanticCodecError::CountTooLarge)?;
    if count > MAX_COLLECTION_ITEMS { return Err(SemanticCodecError::CountTooLarge); }
    out.extend_from_slice(&count.to_be_bytes());
    Ok(())
}

fn encode_tree(tree: &Tree) -> Result<Vec<u8>, SemanticCodecError> {
    tree.validate()?;
    let mut out = Vec::new();
    push_count(&mut out, tree.entries.len())?;
    for (path, entry) in &tree.entries {
        push_blob(&mut out, path);
        out.extend_from_slice(&entry.node_id.0);
        out.push(match entry.kind {
            NodeKind::File => 1,
            NodeKind::Directory => 2,
            NodeKind::Symlink => 3,
        });
        match entry.content {
            Some(content) => {
                out.push(1);
                out.extend_from_slice(&(content.0).0);
            }
            None => out.push(0),
        }
        match entry.derived_from {
            Some(node) => {
                out.push(1);
                out.extend_from_slice(&node.0);
            }
            None => out.push(0),
        }
    }
    Ok(out)
}

fn decode_tree(payload: &[u8]) -> Result<Tree, SemanticCodecError> {
    let mut reader = Reader::new(payload);
    let count = reader.count()?;
    let mut entries = BTreeMap::new();
    let mut previous: Option<Vec<u8>> = None;
    for _ in 0..count {
        let path = reader.blob()?;
        crate::validate_path(&path)?;
        if previous.as_ref().is_some_and(|prev| path.as_slice() <= prev.as_slice()) {
            return Err(SemanticCodecError::NonCanonicalOrder("tree path"));
        }
        previous = Some(path.clone());
        let node_id = reader.node_id()?;
        let kind = match reader.u8()? {
            1 => NodeKind::File,
            2 => NodeKind::Directory,
            3 => NodeKind::Symlink,
            value => return Err(SemanticCodecError::UnknownNodeKind(value)),
        };
        let content = match reader.u8()? {
            0 => None,
            1 => Some(ContentId(reader.object_id()?)),
            value => return Err(SemanticCodecError::InvalidOptionalMarker(value)),
        };
        let derived_from = match reader.u8()? {
            0 => None,
            1 => Some(reader.node_id()?),
            value => return Err(SemanticCodecError::InvalidOptionalMarker(value)),
        };
        if entries.insert(path, NodeEntry { node_id, kind, content, derived_from }).is_some() {
            return Err(SemanticCodecError::DuplicatePath);
        }
    }
    reader.finish()?;
    let tree = Tree { entries };
    tree.validate()?;
    Ok(tree)
}

pub fn encode_semantic(value: &SemanticObject) -> Result<ObjectEnvelope, SemanticCodecError> {
    let payload = match value {
        SemanticObject::Content(bytes) => bytes.clone(),
        SemanticObject::Tree(tree) => encode_tree(tree)?,
        SemanticObject::ChangeVersion(change) => {
            change.validate()?;
            let mut out = Vec::new();
            out.extend_from_slice(&change.change_id.0);
            push_blob(&mut out, &change.message);
            out.extend_from_slice(&change.tree_before.0);
            out.extend_from_slice(&change.tree_after.0);
            out
        }
        SemanticObject::Revision(revision) => {
            revision.validate()?;
            let mut out = Vec::new();
            push_count(&mut out, revision.parents.len())?;
            for parent in &revision.parents {
                out.extend_from_slice(&parent.0);
            }
            out.extend_from_slice(&revision.tree.0);
            match revision.change_version {
                Some(id) => {
                    out.push(1);
                    out.extend_from_slice(&id.0);
                }
                None => out.push(0),
            }
            out
        }
        SemanticObject::View(view) => {
            view.validate()?;
            let mut out = Vec::new();
            push_count(&mut out, view.refs.len())?;
            for (name, id) in &view.refs {
                push_blob(&mut out, name);
                out.extend_from_slice(&id.0);
            }
            push_count(&mut out, view.workspace_heads.len())?;
            for (name, id) in &view.workspace_heads {
                push_blob(&mut out, name);
                out.extend_from_slice(&id.0);
            }
            out
        }
        SemanticObject::Operation(operation) => {
            operation.validate()?;
            let mut out = Vec::new();
            push_count(&mut out, operation.parents.len())?;
            for parent in &operation.parents {
                out.extend_from_slice(&parent.0);
            }
            out.extend_from_slice(&operation.view.0);
            push_blob(&mut out, &operation.command);
            out
        }
        SemanticObject::Conflict(conflict) => {
            conflict.validate()?;
            let mut out = Vec::new();
            push_blob(&mut out, &conflict.kind);
            push_count(&mut out, conflict.inputs.len())?;
            for input in &conflict.inputs {
                out.extend_from_slice(&input.0);
            }
            let mut affected = conflict.affected_nodes.clone();
            affected.sort();
            push_count(&mut out, affected.len())?;
            for node in affected {
                out.extend_from_slice(&node.0);
            }
            out
        }
    };
    Ok(ObjectEnvelope::new(value.object_type(), payload))
}

pub fn decode_semantic(envelope: &ObjectEnvelope) -> Result<SemanticObject, SemanticCodecError> {
    let value = match envelope.object_type {
        ObjectType::Content => SemanticObject::Content(envelope.payload.clone()),
        ObjectType::Tree => SemanticObject::Tree(decode_tree(&envelope.payload)?),
        ObjectType::ChangeVersion => {
            let mut reader = Reader::new(&envelope.payload);
            let value = ChangeVersion {
                change_id: reader.change_id()?,
                message: reader.blob()?,
                tree_before: reader.object_id()?,
                tree_after: reader.object_id()?,
            };
            reader.finish()?;
            value.validate()?;
            SemanticObject::ChangeVersion(value)
        }
        ObjectType::Revision => {
            let mut reader = Reader::new(&envelope.payload);
            let parent_count = reader.count()?;
            let mut parents = Vec::with_capacity(parent_count as usize);
            for _ in 0..parent_count {
                parents.push(reader.object_id()?);
            }
            let tree = reader.object_id()?;
            let change_version = match reader.u8()? {
                0 => None,
                1 => Some(reader.object_id()?),
                value => return Err(SemanticCodecError::InvalidOptionalMarker(value)),
            };
            reader.finish()?;
            let value = Revision { parents, tree, change_version };
            value.validate()?;
            SemanticObject::Revision(value)
        }
        ObjectType::Attestation => {
            let mut reader = Reader::new(&envelope.payload);
            let kind = reader.blob()?;
            let input_count = reader.count()?;
            let mut inputs = Vec::with_capacity(input_count as usize);
            for _ in 0..input_count {
                inputs.push(reader.object_id()?);
            }
            let affected_count = reader.count()?;
            let mut affected_nodes = Vec::with_capacity(affected_count as usize);
            for _ in 0..affected_count {
                affected_nodes.push(reader.node_id()?);
            }
            if !affected_nodes.windows(2).all(|pair| pair[0] < pair[1]) && affected_nodes.len() > 1 {
                return Err(SemanticCodecError::NonCanonicalOrder("conflict affected node"));
            }
            let sig_count = reader.count()?;
            let mut signatures = Vec::with_capacity(sig_count as usize);
            for _ in 0..sig_count {
                signatures.push(reader.blob()?);
            }
            let value = Attestation { kind, inputs, affected_nodes, signatures };
            value.validate()?;
            SemanticObject::Attestation(value)
        }
        ObjectType::ReleaseManifest => {
            let mut reader = Reader::new(&envelope.payload);
            let name_len = reader.u64()? as usize;
            let name = reader.bytes(name_len)?;
            let seq = reader.u64()?;
            let rev_len = reader.u32()? as usize;
            let mut revisions = Vec::with_capacity(rev_len as usize);
            for _ in 0..rev_len {
                revisions.push(reader.object_id()?);
            }
            let mut artifacts = Vec::with_capacity(reader.u32()? as usize);
            let art_count = reader.u32()?;
            for _ in 0..art_count {
                let a_name_len = reader.u32()? as usize;
                let a_name = reader.bytes(a_name_len)?;
                let a_oid = reader.object_id()?;
                artifacts.push((a_name, a_oid));
            }
            let prov_len = reader.u32()? as usize;
            let mut provenance = Vec::with_capacity(prov_len as usize);
            for _ in 0..prov_len {
                provenance.push(reader.object_id()?);
            }
            let value = ReleaseManifest { name, revisions, artifacts, provenance, sequence: seq };
            value.validate()?;
            SemanticObject::ReleaseManifest(value)
        }
        ObjectType::View => {
            let mut reader = Reader::new(&envelope.payload);
            let ref_count = reader.count()?;
            let mut refs = BTreeMap::new();
            let mut previous: Option<Vec<u8>> = None;
            for _ in 0..ref_count {
                let name = reader.blob()?;
                if previous.as_ref().is_some_and(|prev| name.as_slice() <= prev.as_slice()) {
                    return Err(SemanticCodecError::NonCanonicalOrder("ref name"));
                }
                previous = Some(name.clone());
                refs.insert(name, reader.object_id()?);
            }
            let head_count = reader.count()?;
            let mut workspace_heads = BTreeMap::new();
            previous = None;
            for _ in 0..head_count {
                let name = reader.blob()?;
                if previous.as_ref().is_some_and(|prev| name.as_slice() <= prev.as_slice()) {
                    return Err(SemanticCodecError::NonCanonicalOrder("workspace name"));
                }
                previous = Some(name.clone());
                workspace_heads.insert(name, reader.object_id()?);
            }
            reader.finish()?;
            let value = RepositoryView { refs, workspace_heads };
            value.validate()?;
            SemanticObject::View(value)
        }
        ObjectType::Operation => {
            let mut reader = Reader::new(&envelope.payload);
            let parent_count = reader.count()?;
            let mut parents = Vec::with_capacity(parent_count as usize);
            for _ in 0..parent_count {
                parents.push(reader.object_id()?);
            }
            let value = Operation {
                parents,
                view: reader.object_id()?,
                command: reader.blob()?,
            };
            reader.finish()?;
            value.validate()?;
            SemanticObject::Operation(value)
        }
        ObjectType::Conflict => {
            let mut reader = Reader::new(&envelope.payload);
            let kind = reader.blob()?;
            let input_count = reader.count()?;
            let mut inputs = Vec::with_capacity(input_count as usize);
            for _ in 0..input_count {
                inputs.push(reader.object_id()?);
            }
            let affected_count = reader.count()?;
            let mut affected_nodes = Vec::with_capacity(affected_count as usize);
            for _ in 0..affected_count {
                affected_nodes.push(reader.node_id()?);
            }
            if !affected_nodes.windows(2).all(|pair| pair[0] < pair[1]) && affected_nodes.len() > 1 {
                return Err(SemanticCodecError::NonCanonicalOrder("conflict affected node"));
            }
            reader.finish()?;
            let value = Conflict { kind, inputs, affected_nodes };
            value.validate()?;
            SemanticObject::Conflict(value)
        }
    };

    if encode_semantic(&value)? != *envelope {
        return Err(SemanticCodecError::NonCanonical);
    }
    Ok(value)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn content_round_trip() {
        let value = SemanticObject::Content(b"hello".to_vec());
        let envelope = encode_semantic(&value).unwrap();
        assert_eq!(decode_semantic(&envelope).unwrap(), value);
    }

    fn expected_vector(name: &str) -> &'static str {
        include_str!("../../../tests/vectors/semantic-codec-v0.tsv")
            .lines()
            .filter(|line| !line.is_empty() && !line.starts_with('#'))
            .find_map(|line| {
                let (key, value) = line.split_once('\t')?;
                (key == name).then_some(value)
            })
            .unwrap_or_else(|| panic!("missing semantic codec vector: {name}"))
    }

    fn hex(bytes: &[u8]) -> String {
        bytes.iter().map(|byte| format!("{byte:02x}")).collect()
    }

    fn assert_vector(name: &str, value: SemanticObject) {
        let envelope = encode_semantic(&value).unwrap();
        assert_eq!(value.semantic_id().to_hex(), expected_vector(&format!("{name}.semantic_id")));
        assert_eq!(hex(&envelope.encode().unwrap()), expected_vector(&format!("{name}.envelope")));
    }

    #[test]
    fn shared_semantic_vectors_match() {
        let node_a = NodeId([0_u8; 16]);
        let node_b = NodeId([0x11_u8; 16]);
        let content = b"hello".to_vec();
        let content_id = ContentId::from_bytes(&content);
        let mut entries = BTreeMap::new();
        entries.insert(b"README".to_vec(), NodeEntry {
            node_id: node_a, kind: NodeKind::File, content: Some(content_id), derived_from: None,
        });
        entries.insert(b"link".to_vec(), NodeEntry {
            node_id: node_b, kind: NodeKind::Symlink, content: Some(content_id), derived_from: Some(node_a),
        });
        let tree = Tree { entries };
        let change = ChangeVersion {
            change_id: ChangeId([0x22_u8; 16]),
            message: b"message".to_vec(),
            tree_before: ObjectId::digest(b"TREE", &[b"before"]),
            tree_after: tree.id(),
        };
        let revision = Revision {
            parents: vec![ObjectId::digest(b"PARENT", &[b"0"])],
            tree: tree.id(),
            change_version: Some(change.id()),
        };
        let mut refs = BTreeMap::new();
        refs.insert(b"main".to_vec(), revision.id());
        let mut workspace_heads = BTreeMap::new();
        workspace_heads.insert(b"default".to_vec(), revision.id());
        let view = RepositoryView { refs, workspace_heads };
        let operation = Operation { parents: vec![], view: view.id(), command: b"publish".to_vec() };
        let conflict = Conflict {
            kind: b"text".to_vec(),
            inputs: vec![ObjectId::digest(b"SIDE", &[b"a"]), ObjectId::digest(b"SIDE", &[b"b"])],
            affected_nodes: vec![node_b, node_a],
        };

        assert_vector("content.sample", SemanticObject::Content(content));
        assert_vector("tree.sample", SemanticObject::Tree(tree));
        assert_vector("change.sample", SemanticObject::ChangeVersion(change));
        assert_vector("revision.sample", SemanticObject::Revision(revision));
        assert_vector("view.sample", SemanticObject::View(view));
        assert_vector("operation.sample", SemanticObject::Operation(operation));
        assert_vector("conflict.sample", SemanticObject::Conflict(conflict));
    }

    #[test]
    fn conflict_encoding_normalizes_set_like_affected_nodes() {
        let a = NodeId([0_u8; 16]);
        let b = NodeId([1_u8; 16]);
        let sides = vec![ObjectId::digest(b"SIDE", &[b"a"]), ObjectId::digest(b"SIDE", &[b"b"])];
        let first = SemanticObject::Conflict(Conflict {
            kind: b"text".to_vec(),
            inputs: sides.clone(),
            affected_nodes: vec![a, b],
        });
        let second = SemanticObject::Conflict(Conflict {
            kind: b"text".to_vec(),
            inputs: sides,
            affected_nodes: vec![b, a],
        });
        assert_eq!(first.semantic_id(), second.semantic_id());
        assert_eq!(encode_semantic(&first).unwrap(), encode_semantic(&second).unwrap());
    }
}
