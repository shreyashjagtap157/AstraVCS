//! AstraVCS semantic reference model.
//!
//! This crate intentionally favors explicit, easy-to-audit semantics over
//! performance. Production storage and graph implementations must conform to
//! this model rather than replacing its meaning accidentally.

mod codec;
mod ids;
mod model;
mod semantic_codec;

pub use codec::{CodecError, ObjectEnvelope, ObjectType, CODEC_VERSION, MAGIC, MAX_PAYLOAD_BYTES};
pub use ids::{ChangeId, ContentId, NodeId, ObjectId};
pub use semantic_codec::{decode_semantic, encode_semantic, SemanticCodecError, SemanticObject, MAX_COLLECTION_ITEMS};
pub use model::{
    validate_path, ChangeVersion, Conflict, HistoryError, NodeEntry, NodeKind, Operation,
    RepositoryHistory, RepositoryView, Revision, Tree, ValidationError, MAX_NAME_BYTES,
    MAX_PATH_BYTES,
};
