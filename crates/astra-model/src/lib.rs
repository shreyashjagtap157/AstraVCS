//! AstraVCS semantic reference model.
//!
//! This crate intentionally favors explicit, easy-to-audit semantics over
//! performance. Production storage and graph implementations must conform to
//! this model rather than replacing its meaning accidentally.

mod ids;
mod model;

pub use ids::{ChangeId, ContentId, NodeId, ObjectId};
pub use model::{
    ChangeVersion, Conflict, NodeEntry, NodeKind, Operation, RepositoryView,
    Revision, Tree,
};
