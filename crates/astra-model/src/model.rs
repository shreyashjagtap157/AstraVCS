use crate::{ChangeId, ContentId, NodeId, ObjectId};
use std::collections::BTreeMap;

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

#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct Tree {
    pub entries: BTreeMap<Vec<u8>, NodeEntry>,
}

impl Tree {
    pub fn rename(&mut self, from: &[u8], to: Vec<u8>) -> Result<(), &'static str> {
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
        self.entries.insert(to, copied);
        Ok(new_id)
    }

    pub fn semantic_bytes(&self) -> Vec<u8> {
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
    pub fn id(&self) -> ObjectId {
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
    pub fn id(&self) -> ObjectId {
        let mut parent_bytes = Vec::with_capacity(self.parents.len() * 32);
        for parent in &self.parents {
            parent_bytes.extend_from_slice(&parent.0);
        }
        let cv = self.change_version.map(|id| id.0).unwrap_or([0_u8; 32]);
        ObjectId::digest(
            b"ASTRA:REVISION:V0",
            &[&parent_bytes, &self.tree.0, &cv],
        )
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Conflict {
    pub kind: Vec<u8>,
    pub inputs: Vec<ObjectId>,
    pub affected_nodes: Vec<NodeId>,
}

impl Conflict {
    pub fn id(&self) -> ObjectId {
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

#[derive(Clone, Debug, Default, Eq, PartialEq)]
pub struct RepositoryView {
    pub refs: BTreeMap<Vec<u8>, ObjectId>,
    pub workspace_heads: BTreeMap<Vec<u8>, ObjectId>,
}

impl RepositoryView {
    pub fn id(&self) -> ObjectId {
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
    pub fn id(&self) -> ObjectId {
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
    fn amend_preserves_change_id_but_changes_version_id() {
        let change_id = ChangeId::from_bytes([4; 16]);
        let before = ObjectId::digest(b"TEST", &[b"before"]);
        let after = ObjectId::digest(b"TEST", &[b"after"]);
        let after2 = ObjectId::digest(b"TEST", &[b"after2"]);
        let v1 = ChangeVersion {
            change_id,
            message: b"first".to_vec(),
            tree_before: before,
            tree_after: after,
        };
        let v2 = v1.amended(b"second".to_vec(), after2);
        assert_eq!(v1.change_id, v2.change_id);
        assert_ne!(v1.id(), v2.id());
    }

    #[test]
    fn rebase_changes_revision_id_without_changing_change_version() {
        let tree = ObjectId::digest(b"TEST", &[b"tree"]);
        let cv = ObjectId::digest(b"TEST", &[b"change-version"]);
        let parent_a = ObjectId::digest(b"TEST", &[b"parent-a"]);
        let parent_b = ObjectId::digest(b"TEST", &[b"parent-b"]);
        let a = Revision { parents: vec![parent_a], tree, change_version: Some(cv) };
        let b = Revision { parents: vec![parent_b], tree, change_version: Some(cv) };
        assert_eq!(a.change_version, b.change_version);
        assert_ne!(a.id(), b.id());
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
    fn conflict_affected_node_order_is_canonical() {
        let left = ObjectId::digest(b"TEST", &[b"left"]);
        let right = ObjectId::digest(b"TEST", &[b"right"]);
        let node_a = NodeId::from_bytes([0; 16]);
        let node_b = NodeId::from_bytes([1; 16]);
        let a = Conflict {
            kind: b"text/text".to_vec(),
            inputs: vec![left, right],
            affected_nodes: vec![node_a, node_b],
        };
        let b = Conflict {
            kind: b"text/text".to_vec(),
            inputs: vec![left, right],
            affected_nodes: vec![node_b, node_a],
        };
        assert_eq!(a.id(), b.id());
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
