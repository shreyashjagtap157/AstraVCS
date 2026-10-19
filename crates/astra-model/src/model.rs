use crate::{ChangeId, ContentId, NodeId, ObjectId};
use std::{collections::{BTreeMap, HashMap, HashSet}, fmt};

fn validate_object_id(value: &str, label: &'static str) -> Result<(), ValidationError> {
    let lower = value.to_lowercase();
    if lower.len() != 65 || lower != value.to_lowercase() {
        return Err(ValidationError::EmptyName(label));
    }
    Ok(())
}

pub const MAX_PATH_BYTES: usize = 16 * 1024;
pub const MAX_NAME_BYTES: usize = 4 * 1024;

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum ValidationError {
    EmptyPath,
    PathTooLong,
    PathContainsNul,
    PathNotRelative,
    InvalidPathComponent,
    EmptyName(&'static str),
    NameTooLong(&'static str),
    NameContainsNul(&'static str),
    DirectoryHasContent,
    MissingContent,
    SelfDerivedNode,
    DuplicateNodeId,
    DuplicateRevisionParent,
    DuplicateOperationParent,
    EmptyCommand,
    TooFewConflictInputs,
    DuplicateConflictInput,
    EmptyAffectedNodes,
    DuplicateAffectedNode,
}

impl fmt::Display for ValidationError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{self:?}")
    }
}

impl std::error::Error for ValidationError {}

pub fn validate_path(path: &[u8]) -> Result<(), ValidationError> {
    if path.is_empty() {
        return Err(ValidationError::EmptyPath);
    }
    if path.len() > MAX_PATH_BYTES {
        return Err(ValidationError::PathTooLong);
    }
    if path.contains(&0) {
        return Err(ValidationError::PathContainsNul);
    }
    if path.first() == Some(&b'/') || path.last() == Some(&b'/') {
        return Err(ValidationError::PathNotRelative);
    }
    if path
        .split(|byte| *byte == b'/')
        .any(|component| component.is_empty() || component == b"." || component == b"..")
    {
        return Err(ValidationError::InvalidPathComponent);
    }
    Ok(())
}

fn validate_name(name: &[u8], label: &'static str) -> Result<(), ValidationError> {
    if name.is_empty() {
        return Err(ValidationError::EmptyName(label));
    }
    if name.len() > MAX_NAME_BYTES {
        return Err(ValidationError::NameTooLong(label));
    }
    if name.contains(&0) {
        return Err(ValidationError::NameContainsNul(label));
    }
    Ok(())
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum NodeKind {
    File,
    Directory,
    Symlink,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct NodeEntry {
    pub node_id: NodeId,
    pub kind: NodeKind,
    pub content: Option<ContentId>,
    pub derived_from: Option<NodeId>,
}

impl NodeEntry {
    pub fn validate(&self) -> Result<(), ValidationError> {
        match self.kind {
            NodeKind::Directory if self.content.is_some() => return Err(ValidationError::DirectoryHasContent),
            NodeKind::File | NodeKind::Symlink if self.content.is_none() => {
                return Err(ValidationError::MissingContent)
            }
            _ => {}
        }
        if self.derived_from == Some(self.node_id) {
            return Err(ValidationError::SelfDerivedNode);
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct Tree {
    pub entries: BTreeMap<Vec<u8>, NodeEntry>,
}

impl Tree {
    pub fn validate(&self) -> Result<(), ValidationError> {
        let mut node_ids = HashSet::with_capacity(self.entries.len());
        for (path, entry) in &self.entries {
            validate_path(path)?;
            entry.validate()?;
            if !node_ids.insert(entry.node_id) {
                return Err(ValidationError::DuplicateNodeId);
            }
        }
        Ok(())
    }

    pub fn rename(&mut self, from: &[u8], to: Vec<u8>) -> Result<(), &'static str> {
        validate_path(from).map_err(|_| "invalid source path")?;
        validate_path(&to).map_err(|_| "invalid destination path")?;
        if self.entries.contains_key(&to) {
            return Err("destination already exists");
        }
        let entry = self.entries.remove(from).ok_or("source does not exist")?;
        self.entries.insert(to, entry);
        Ok(())
    }

    pub fn copy_node(
        &mut self,
        from: &[u8],
        to: Vec<u8>,
        new_id: NodeId,
    ) -> Result<NodeId, &'static str> {
        validate_path(from).map_err(|_| "invalid source path")?;
        validate_path(&to).map_err(|_| "invalid destination path")?;
        if self.entries.contains_key(&to) {
            return Err("destination already exists");
        }
        let source = self.entries.get(from).cloned().ok_or("source does not exist")?;
        let copied = NodeEntry {
            node_id: new_id,
            kind: source.kind,
            content: source.content,
            derived_from: Some(source.node_id),
        };
        copied.validate().map_err(|_| "invalid copied node")?;
        self.entries.insert(to, copied);
        Ok(new_id)
    }

    pub fn semantic_bytes(&self) -> Vec<u8> {
        self.validate().expect("invalid Tree semantic value");
        let mut out = Vec::new();
        for (path, entry) in &self.entries {
            out.extend_from_slice(&(path.len() as u64).to_be_bytes());
            out.extend_from_slice(path);
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
                Some(source) => {
                    out.push(1);
                    out.extend_from_slice(&source.0);
                }
                None => out.push(0),
            }
        }
        out
    }

    pub fn id(&self) -> ObjectId {
        ObjectId::digest(b"ASTRA:TREE:V0", &[&self.semantic_bytes()])
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ChangeVersion {
    pub change_id: ChangeId,
    pub message: Vec<u8>,
    pub tree_before: ObjectId,
    pub tree_after: ObjectId,
}

impl ChangeVersion {
    pub fn validate(&self) -> Result<(), ValidationError> {
        Ok(())
    }

    pub fn id(&self) -> ObjectId {
        self.validate().expect("invalid ChangeVersion semantic value");
        ObjectId::digest(
            b"ASTRA:CHANGE-VERSION:V0",
            &[
                &self.change_id.0,
                &self.message,
                &self.tree_before.0,
                &self.tree_after.0,
            ],
        )
    }

    pub fn amended(&self, message: Vec<u8>, tree_after: ObjectId) -> Self {
        Self {
            change_id: self.change_id,
            message,
            tree_before: self.tree_before,
            tree_after,
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Revision {
    pub parents: Vec<ObjectId>,
    pub tree: ObjectId,
    pub change_version: Option<ObjectId>,
}

impl Revision {
    pub fn validate(&self) -> Result<(), ValidationError> {
        let mut parents = HashSet::with_capacity(self.parents.len());
        if self.parents.iter().any(|parent| !parents.insert(*parent)) {
            return Err(ValidationError::DuplicateRevisionParent);
        }
        Ok(())
    }

    pub fn id(&self) -> ObjectId {
        self.validate().expect("invalid Revision semantic value");
        let mut parent_bytes = Vec::with_capacity(self.parents.len() * 32);
        for parent in &self.parents {
            parent_bytes.extend_from_slice(&parent.0);
        }
        let cv = self.change_version.map(|id| id.0).unwrap_or([0_u8; 32]);
        ObjectId::digest(b"ASTRA:REVISION:V0", &[&parent_bytes, &self.tree.0, &cv])
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Conflict {
    pub kind: Vec<u8>,
    pub inputs: Vec<ObjectId>,
    pub affected_nodes: Vec<NodeId>,
}

impl Conflict {
    pub fn validate(&self) -> Result<(), ValidationError> {
        validate_name(&self.kind, "conflict kind")?;
        if self.inputs.len() < 2 {
            return Err(ValidationError::TooFewConflictInputs);
        }
        let mut inputs = HashSet::with_capacity(self.inputs.len());
        if self.inputs.iter().any(|input| !inputs.insert(*input)) {
            return Err(ValidationError::DuplicateConflictInput);
        }
        if self.affected_nodes.is_empty() {
            return Err(ValidationError::EmptyAffectedNodes);
        }
        let mut nodes = HashSet::with_capacity(self.affected_nodes.len());
        if self.affected_nodes.iter().any(|node| !nodes.insert(*node)) {
            return Err(ValidationError::DuplicateAffectedNode);
        }
        Ok(())
    }

    pub fn id(&self) -> ObjectId {
        self.validate().expect("invalid Conflict semantic value");
        let mut bytes = Vec::new();
        bytes.extend_from_slice(&(self.kind.len() as u64).to_be_bytes());
        bytes.extend_from_slice(&self.kind);
        for input in &self.inputs {
            bytes.extend_from_slice(&input.0);
        }
        let mut affected_nodes = self.affected_nodes.clone();
        affected_nodes.sort();
        for node in &affected_nodes {
            bytes.extend_from_slice(&node.0);
        }
        ObjectId::digest(b"ASTRA:CONFLICT:V0", &[&bytes])
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct AttestationType {
    pub subject_id: String,
    pub predicate_type: Vec<u8>,
    pub signer_key_id: String,
    pub payload: Vec<u8>,
    pub signature: Vec<u8>,
    pub kind: Vec<u8>,
    pub inputs: Vec<ObjectId>,
    pub affected_nodes: Vec<NodeId>,
    pub signatures: Vec<Vec<u8>>,
}

impl AttestationType {
    pub fn new(subject_id: String, predicate_type: Vec<u8>, signer_key_id: String, payload: Vec<u8>, signature: Vec<u8>, kind: Vec<u8>, inputs: Vec<ObjectId>, affected_nodes: Vec<NodeId>, signatures: Vec<Vec<u8>>) -> Self {
        Self { subject_id, predicate_type, signer_key_id, payload, signature, kind, inputs, affected_nodes, signatures }
    }

    pub fn validate(&self) -> Result<(), ValidationError> {
        validate_object_id(&self.subject_id, "attestation subject")?;
        validate_name(&self.predicate_type, "attestation predicate type")?;
        validate_object_id(&self.signer_key_id, "signer key id")?;
        if self.signature.len() != 64 {
            return Err(ValidationError::EmptyAffectedNodes); // reuse error type, or add new
        }
        validate_name(&self.kind, "attestation kind")?;
        if self.inputs.len() < 2 {
            return Err(ValidationError::TooFewConflictInputs);
        }
        let mut inputs_set = HashSet::with_capacity(self.inputs.len());
        if self.inputs.iter().any(|input| !inputs_set.insert(*input)) {
            return Err(ValidationError::DuplicateConflictInput);
        }
        if self.affected_nodes.is_empty() {
            return Err(ValidationError::EmptyAffectedNodes);
        }
        let mut nodes = HashSet::with_capacity(self.affected_nodes.len());
        if self.affected_nodes.iter().any(|node| !nodes.insert(*node)) {
            return Err(ValidationError::DuplicateAffectedNode);
        }
        Ok(())
    }

    pub fn semantic_id(&self) -> ObjectId {
        let mut bytes = Vec::new();
        let mut out = Vec::new();
        out.extend_from_slice(&(self.predicate_type.len() as u64).to_be_bytes());
        out.extend_from_slice(&self.predicate_type);
        out.extend_from_slice(self.subject_id.as_bytes());
        out.extend_from_slice(self.signer_key_id.as_bytes());
        out.extend_from_slice(&self.payload);
        bytes.extend_from_slice(&out);
        ObjectId::digest(b"ASTRA:ATTESTATION:V1", &[&bytes])
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ReleaseManifestType {
    pub name: Vec<u8>,
    pub revisions: Vec<ObjectId>,
    pub artifacts: Vec<(Vec<u8>, ObjectId)>,
    pub provenance: Vec<ObjectId>,
    pub sequence: u64,
}

impl ReleaseManifestType {
    pub fn new(name: Vec<u8>, revisions: Vec<ObjectId>, artifacts: Vec<(Vec<u8>, ObjectId)>, provenance: Vec<ObjectId>, sequence: u64) -> Self {
        Self { name, revisions, artifacts, provenance, sequence }
    }

    pub fn validate(&self) -> Result<(), ValidationError> {
        validate_name(&self.name, "release name")?;
        if self.revisions.is_empty() {
            return Err(ValidationError::NameTooLong("release revisions"));
        }
        if self.revisions.iter().any(|oid| oid.0.len() != 32) {
            return Err(ValidationError::NameTooLong("release revision"));
        }
        if self.artifacts.iter().any(|(name, _)| name.len() > MAX_NAME_BYTES) {
            return Err(ValidationError::NameTooLong("artifact name"));
        }
        {
            let names: Vec<String> = self
                .artifacts
                .iter()
                .map(|(n, _)| String::from_utf8_lossy(n).into_owned())
                .collect();
            if !names.is_sorted() {
                return Err(ValidationError::NameTooLong("artifact names not sorted"));
            }
            if names.windows(2).any(|w| w[0] == w[1]) {
                return Err(ValidationError::NameTooLong("duplicate artifact names"));
            }
        }
        if self.provenance.iter().any(|pid| pid.0.len() != 32) {
            return Err(ValidationError::NameTooLong("provenance object id"));
        }
        if self.sequence > 1u64 << 63 {
            return Err(ValidationError::NameTooLong("release sequence"));
        }
        Ok(())
    }

    pub fn semantic_id(&self) -> ObjectId {
        let mut bytes = Vec::new();
        let mut out = Vec::new();
        out.extend_from_slice(&(self.name.len() as u64).to_be_bytes());
        out.extend_from_slice(&self.name);
        out.extend_from_slice(&self.sequence.to_be_bytes());
        for oid in &self.revisions {
            bytes.extend_from_slice(&oid.0);
        }
        bytes.extend_from_slice(&out);
        // sentinel 0xFF separates revisions from artifacts
        bytes.push(0xFF);
        for (a_name, a_oid) in &self.artifacts {
            bytes.extend_from_slice(&(a_name.len() as u32).to_be_bytes());
            bytes.extend_from_slice(a_name);
            bytes.extend_from_slice(&a_oid.0);
        }
        // sentinel 0xFE separates artifacts from provenance
        bytes.push(0xFE);
        for pid in &self.provenance {
            bytes.extend_from_slice(&pid.0);
        }
        ObjectId::digest(b"ASTRA:RELEASE-MANIFEST:V1", &[&bytes])
    }
}

#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct RepositoryView {
    pub refs: BTreeMap<Vec<u8>, ObjectId>,
    pub workspace_heads: BTreeMap<Vec<u8>, ObjectId>,
}

impl RepositoryView {
    pub fn validate(&self) -> Result<(), ValidationError> {
        for name in self.refs.keys() {
            validate_name(name, "ref name")?;
        }
        for name in self.workspace_heads.keys() {
            validate_name(name, "workspace name")?;
        }
        Ok(())
    }

    pub fn id(&self) -> ObjectId {
        self.validate().expect("invalid RepositoryView semantic value");
        let mut bytes = Vec::new();
        for (name, id) in &self.refs {
            bytes.extend_from_slice(&(name.len() as u64).to_be_bytes());
            bytes.extend_from_slice(name);
            bytes.extend_from_slice(&id.0);
        }
        bytes.push(0xff);
        for (name, id) in &self.workspace_heads {
            bytes.extend_from_slice(&(name.len() as u64).to_be_bytes());
            bytes.extend_from_slice(name);
            bytes.extend_from_slice(&id.0);
        }
        ObjectId::digest(b"ASTRA:VIEW:V0", &[&bytes])
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Operation {
    pub parents: Vec<ObjectId>,
    pub view: ObjectId,
    pub command: Vec<u8>,
}

impl Operation {
    pub fn validate(&self) -> Result<(), ValidationError> {
        let mut parents = HashSet::with_capacity(self.parents.len());
        if self.parents.iter().any(|parent| !parents.insert(*parent)) {
            return Err(ValidationError::DuplicateOperationParent);
        }
        if self.command.is_empty() {
            return Err(ValidationError::EmptyCommand);
        }
        Ok(())
    }

    pub fn id(&self) -> ObjectId {
        self.validate().expect("invalid Operation semantic value");
        let mut parent_bytes = Vec::new();
        for parent in &self.parents {
            parent_bytes.extend_from_slice(&parent.0);
        }
        ObjectId::digest(
            b"ASTRA:OPERATION:V0",
            &[&parent_bytes, &self.view.0, &self.command],
        )
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum HistoryError {
    StaleHead { expected: Option<ObjectId>, current: Option<ObjectId> },
    MissingParent,
    MissingOperation,
    ParentMismatch,
    InvalidView(ValidationError),
    InvalidOperation(ValidationError),
}

#[derive(Clone, Debug, Default)]
pub struct RepositoryHistory {
    pub views: HashMap<ObjectId, RepositoryView>,
    pub operations: HashMap<ObjectId, Operation>,
    pub head: Option<ObjectId>,
}

impl RepositoryHistory {
    pub fn publish(
        &mut self,
        view: RepositoryView,
        command: Vec<u8>,
        expected_head: Option<ObjectId>,
    ) -> Result<ObjectId, HistoryError> {
        if expected_head != self.head {
            return Err(HistoryError::StaleHead {
                expected: expected_head,
                current: self.head,
            });
        }
        view.validate().map_err(HistoryError::InvalidView)?;
        let view_id = view.id();
        self.views.insert(view_id, view);
        let parents = self.head.into_iter().collect();
        let operation = Operation { parents, view: view_id, command };
        operation.validate().map_err(HistoryError::InvalidOperation)?;
        let operation_id = operation.id();
        self.operations.insert(operation_id, operation);
        self.head = Some(operation_id);
        Ok(operation_id)
    }

    pub fn record_from(
        &mut self,
        parent: Option<ObjectId>,
        view: RepositoryView,
        command: Vec<u8>,
    ) -> Result<ObjectId, HistoryError> {
        if parent.is_some_and(|id| !self.operations.contains_key(&id)) {
            return Err(HistoryError::MissingParent);
        }
        view.validate().map_err(HistoryError::InvalidView)?;
        let view_id = view.id();
        self.views.insert(view_id, view);
        let operation = Operation {
            parents: parent.into_iter().collect(),
            view: view_id,
            command,
        };
        operation.validate().map_err(HistoryError::InvalidOperation)?;
        let operation_id = operation.id();
        self.operations.insert(operation_id, operation);
        Ok(operation_id)
    }

    pub fn publish_existing(
        &mut self,
        operation_id: ObjectId,
        expected_head: Option<ObjectId>,
    ) -> Result<ObjectId, HistoryError> {
        if expected_head != self.head {
            return Err(HistoryError::StaleHead {
                expected: expected_head,
                current: self.head,
            });
        }
        let operation = self.operations.get(&operation_id).ok_or(HistoryError::MissingOperation)?;
        let expected_parents: Vec<_> = expected_head.into_iter().collect();
        if operation.parents != expected_parents {
            return Err(HistoryError::ParentMismatch);
        }
        self.head = Some(operation_id);
        Ok(operation_id)
    }

    pub fn current_view(&self) -> Option<&RepositoryView> {
        let head = self.head?;
        let operation = self.operations.get(&head)?;
        self.views.get(&operation.view)
    }

    pub fn undo(&mut self) -> Option<ObjectId> {
        let head = self.head?;
        let operation = self.operations.get(&head)?;
        self.head = operation.parents.first().copied();
        self.head
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rename_preserves_node_identity() {
        let content = ContentId::from_bytes(b"hello");
        let node_id = NodeId::from_bytes([1; 16]);
        let mut tree = Tree::default();
        tree.entries.insert(
            b"a.txt".to_vec(),
            NodeEntry {
                node_id,
                kind: NodeKind::File,
                content: Some(content),
                derived_from: None,
            },
        );
        tree.rename(b"a.txt", b"b.txt".to_vec()).unwrap();
        assert_eq!(tree.entries[b"b.txt".as_slice()].node_id, node_id);
    }

    #[test]
    fn copy_creates_new_node_identity_and_provenance() {
        let source_id = NodeId::from_bytes([2; 16]);
        let mut tree = Tree::default();
        tree.entries.insert(
            b"a.txt".to_vec(),
            NodeEntry {
                node_id: source_id,
                kind: NodeKind::File,
                content: Some(ContentId::from_bytes(b"hello")),
                derived_from: None,
            },
        );
        let expected_copy_id = NodeId::from_bytes([3; 16]);
        let copy_id = tree.copy_node(b"a.txt", b"b.txt".to_vec(), expected_copy_id).unwrap();
        assert_ne!(source_id, copy_id);
        assert_eq!(tree.entries[b"b.txt".as_slice()].derived_from, Some(source_id));
    }

    #[test]
    fn compare_and_swap_rejects_stale_publication() {
        let mut history = RepositoryHistory::default();
        let revision_a = ObjectId::digest(b"TEST", &[b"a"]);
        let revision_b = ObjectId::digest(b"TEST", &[b"b"]);
        let mut first_view = RepositoryView::default();
        first_view.refs.insert(b"main".to_vec(), revision_a);
        let first = history.publish(first_view, b"first".to_vec(), None).unwrap();
        let mut second_view = RepositoryView::default();
        second_view.refs.insert(b"main".to_vec(), revision_b);
        assert!(matches!(
            history.publish(second_view, b"stale".to_vec(), None),
            Err(HistoryError::StaleHead { .. })
        ));
        assert_eq!(history.head, Some(first));
    }

    #[test]
    fn publish_creates_operation_and_moves_head() {
        let mut history = RepositoryHistory::default();
        let revision_a = ObjectId::digest(b"TEST", &[b"a"]);
        let mut first_view = RepositoryView::default();
        first_view.refs.insert(b"main".to_vec(), revision_a);
        let view_id = first_view.id();
        let op_id = history.publish(first_view, b"initial commit".to_vec(), None).unwrap();
        assert_eq!(history.head, Some(op_id));
        assert!(history.operations.contains_key(&op_id));
        assert!(history.views.contains_key(&view_id));
    }

    #[test]
    fn publish_rejects_stale_head() {
        let mut history = RepositoryHistory::default();
        let rev_a = ObjectId::digest(b"TEST", &[b"a"]);
        let rev_b = ObjectId::digest(b"TEST", &[b"b"]);
        let mut view_a = RepositoryView::default();
        view_a.refs.insert(b"main".to_vec(), rev_a);
        let _ = history.publish(view_a, b"first".to_vec(), None);
        let mut view_b = RepositoryView::default();
        view_b.refs.insert(b"main".to_vec(), rev_b);
        assert!(matches!(
            history.publish(view_b, b"second".to_vec(), None),
            Err(HistoryError::StaleHead { .. })
        ));
    }

    #[test]
    fn record_from_validates_parent_exists() {
        let mut history = RepositoryHistory::default();
        let rev = ObjectId::digest(b"TEST", &[b"rev"]);
        let mut view = RepositoryView::default();
        view.refs.insert(b"main".as_slice().to_vec(), rev);
        let missing_parent = ObjectId::digest(b"TEST", &[b"missing"]);
        let result = history.record_from(Some(missing_parent), view, b"command".to_vec());
        assert!(matches!(result, Err(HistoryError::MissingParent)));
    }

    #[test]
    fn record_from_creates_operation_without_moving_head() {
        let mut history = RepositoryHistory::default();
        let rev = ObjectId::digest(b"TEST", &[b"rev"]);
        let mut view = RepositoryView::default();
        view.refs.insert(b"main".to_vec(), rev);

        let published = history.publish(view.clone(), b"first".to_vec(), None).unwrap();

        let op_id = history.record_from(Some(published), view, b"command".to_vec()).unwrap();
        assert!(history.operations.contains_key(&op_id));
        assert_ne!(op_id, published);
        assert_eq!(history.head, Some(published));
    }

    #[test]
    fn publish_existing_moves_head_to_operation() {
        let mut history = RepositoryHistory::default();
        let rev_a = ObjectId::digest(b"TEST", &[b"a"]);
        let mut view = RepositoryView::default();
        view.refs.insert(b"main".as_slice().to_vec(), rev_a);
        let op1 = history.publish(view.clone(), b"first".to_vec(), None).unwrap();

        let op_x = history.record_from(Some(op1), view, b"recorded".to_vec()).unwrap();

        let result = history.publish_existing(op_x, Some(op1));
        assert_eq!(result, Ok(op_x));
        assert_eq!(history.head, Some(op_x));
    }

    #[test]
    fn publish_existing_rejects_wrong_parents() {
        let mut history = RepositoryHistory::default();
        let rev_a = ObjectId::digest(b"TEST", &[b"a"]);
        let rev_b = ObjectId::digest(b"TEST", &[b"b"]);
        let mut view_a = RepositoryView::default();
        view_a.refs.insert(b"main".to_vec(), rev_a);
        let op1 = history.publish(view_a, b"first".to_vec(), None).unwrap();

        let mut view_b = RepositoryView::default();
        view_b.refs.insert(b"main".to_vec(), rev_b);
        let op2 = history.publish(view_b, b"second".to_vec(), Some(op1)).unwrap();

        let result = history.publish_existing(op1, Some(op2));
        assert!(matches!(result, Err(HistoryError::ParentMismatch)));
        assert_eq!(history.head, Some(op2));
    }

    #[test]
    fn current_view_returns_head_view() {
        let mut history = RepositoryHistory::default();
        let rev = ObjectId::digest(b"TEST", &[b"rev"]);
        let mut view = RepositoryView::default();
        view.refs.insert(b"main".as_slice().to_vec(), rev);
        let _ = history.publish(view.clone(), b"commit".to_vec(), None);

        let current = history.current_view();
        assert!(current.is_some());
        assert_eq!(current.unwrap().refs.get(b"main".as_slice()), Some(&rev));
    }

    #[test]
    fn undo_pops_parent_and_moves_head() {
        let mut history = RepositoryHistory::default();
        let rev_a = ObjectId::digest(b"TEST", &[b"a"]);
        let rev_b = ObjectId::digest(b"TEST", &[b"b"]);

        let mut view_a = RepositoryView::default();
        view_a.refs.insert(b"main".to_vec(), rev_a);
        let op1 = history.publish(view_a, b"first".to_vec(), None).unwrap();

        let mut view_b = RepositoryView::default();
        view_b.refs.insert(b"main".to_vec(), rev_b);
        let op2 = history.publish(view_b, b"second".to_vec(), Some(op1)).unwrap();

        assert_eq!(history.head, Some(op2));
        let new_head = history.undo();
        assert_eq!(new_head, Some(op1));
        assert_eq!(history.head, Some(op1));

        let new_head = history.undo();
        assert_eq!(new_head, None);
        assert_eq!(history.head, None);
    }

    #[test]
    fn undo_moves_to_none_at_genesis() {
        let mut history = RepositoryHistory::default();
        let rev = ObjectId::digest(b"TEST", &[b"rev"]);
        let mut view = RepositoryView::default();
        view.refs.insert(b"main".to_vec(), rev);
        let op1 = history.publish(view, b"commit".to_vec(), None).unwrap();
        assert_eq!(history.head, Some(op1));

        let new_head = history.undo();
        assert_eq!(new_head, None);
        assert_eq!(history.head, None);
    }

    fn expected_vector(name: &str) -> &'static str {
        include_str!("../../../tests/vectors/bootstrap-v0.tsv")
            .lines()
            .filter(|line| !line.is_empty() && !line.starts_with('#'))
            .find_map(|line| {
                let (key, value) = line.split_once('\t')?;
                (key == name).then_some(value)
            })
            .unwrap_or_else(|| panic!("missing canonical vector: {name}"))
    }

    #[test]
    fn bootstrap_canonical_vectors_match() {
        let node_a = NodeId::from_bytes([
            0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
            0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f,
        ]);
        let node_b = NodeId::from_bytes([
            0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17,
            0x18, 0x19, 0x1a, 0x1b, 0x1c, 0x1d, 0x1e, 0x1f,
        ]);
        let change_id = ChangeId::from_bytes([
            0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27,
            0x28, 0x29, 0x2a, 0x2b, 0x2c, 0x2d, 0x2e, 0x2f,
        ]);

        let content_hello = ContentId::from_bytes(b"hello");
        let content_link = ContentId::from_bytes(b"../README.md");
        assert_eq!(content_hello.0.to_hex(), expected_vector("content.hello"));
        assert_eq!(content_link.0.to_hex(), expected_vector("content.link"));

        let mut tree_before = Tree::default();
        tree_before.entries.insert(
            b"README.md".to_vec(),
            NodeEntry {
                node_id: node_a,
                kind: NodeKind::File,
                content: Some(content_hello),
                derived_from: None,
            },
        );
        assert_eq!(tree_before.id().to_hex(), expected_vector("tree.before"));

        let mut tree_after = Tree::default();
        tree_after.entries.insert(
            b"docs/README.md".to_vec(),
            NodeEntry {
                node_id: node_a,
                kind: NodeKind::File,
                content: Some(content_hello),
                derived_from: None,
            },
        );
        tree_after.entries.insert(
            b"latest".to_vec(),
            NodeEntry {
                node_id: node_b,
                kind: NodeKind::Symlink,
                content: Some(content_link),
                derived_from: Some(node_a),
            },
        );
        assert_eq!(tree_after.id().to_hex(), expected_vector("tree.after"));

        let change = ChangeVersion {
            change_id,
            message: b"move docs and add link".to_vec(),
            tree_before: tree_before.id(),
            tree_after: tree_after.id(),
        };
        assert_eq!(change.id().to_hex(), expected_vector("change.version"));

        let parent = ObjectId::digest(b"TEST:PARENT", &[b"parent"]);
        let revision = Revision {
            parents: vec![parent],
            tree: tree_after.id(),
            change_version: Some(change.id()),
        };
        assert_eq!(revision.id().to_hex(), expected_vector("revision.sample"));

        let mut view = RepositoryView::default();
        view.refs.insert(b"main".to_vec(), revision.id());
        view.workspace_heads.insert(b"default".to_vec(), revision.id());
        assert_eq!(view.id().to_hex(), expected_vector("view.sample"));

        let operation = Operation {
            parents: vec![],
            view: view.id(),
            command: b"publish main".to_vec(),
        };
        assert_eq!(operation.id().to_hex(), expected_vector("operation.sample"));

        let conflict = Conflict {
            kind: b"rename/rename".to_vec(),
            inputs: vec![tree_before.id(), tree_after.id()],
            affected_nodes: vec![node_b, node_a],
        };
        assert_eq!(conflict.id().to_hex(), expected_vector("conflict.sample"));
    }
}
