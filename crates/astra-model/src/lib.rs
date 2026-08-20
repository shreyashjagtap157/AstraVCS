//! AstraVCS semantic reference model.
//!
//! This crate intentionally favors explicit, easy-to-audit semantics over
//! performance. Production storage and graph implementations must conform to
//! this model rather than replacing its meaning accidentally.

mod codec;
mod ids;
mod model;

pub use codec::{CodecError, ObjectEnvelope, ObjectType, CODEC_VERSION, MAGIC, MAX_PAYLOAD_BYTES};
pub use ids::{ChangeId, ContentId, NodeId, ObjectId};
pub use model::{
    validate_path, ChangeVersion, Conflict, HistoryError, NodeEntry, NodeKind, Operation,
    RepositoryHistory, RepositoryView, Revision, Tree, ValidationError, MAX_NAME_BYTES,
    MAX_PATH_BYTES,
};
