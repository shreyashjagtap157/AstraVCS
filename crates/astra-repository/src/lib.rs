//! Bootstrap AstraVCS repository persistence.
//!
//! This crate maps semantic object IDs onto bootstrap loose-store keys without
//! making the physical StoreKey part of semantic repository identity.

use astra_model::{decode_semantic, encode_semantic, ObjectId, ObjectType, SemanticCodecError, SemanticObject};
use astra_store::{LooseObjectStore, StoreError, StoreKey};
use std::collections::HashSet;
use std::fmt;
use std::fs::{self, File, OpenOptions};
use std::io::{self, Read, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};

pub const REPOSITORY_FORMAT: &[u8] = b"ASTRA-BOOTSTRAP-REPOSITORY\nversion=0\n";
static UNIQUE_COUNTER: AtomicU64 = AtomicU64::new(0);

#[derive(Debug)]
pub enum RepositoryError {
    Io(io::Error),
    Store(StoreError),
    SemanticCodec(SemanticCodecError),
    Exists,
    MissingMetadata,
    UnsupportedFormat,
    MissingSemanticObject(ObjectId),
    MalformedMapping,
    MappingCollision,
    WrongObjectType,
    SemanticMismatch,
}

impl fmt::Display for RepositoryError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{self:?}")
    }
}

impl std::error::Error for RepositoryError {}

impl From<io::Error> for RepositoryError {
    fn from(value: io::Error) -> Self { Self::Io(value) }
}
impl From<StoreError> for RepositoryError {
    fn from(value: StoreError) -> Self { Self::Store(value) }
}
impl From<SemanticCodecError> for RepositoryError {
    fn from(value: SemanticCodecError) -> Self { Self::SemanticCodec(value) }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct StoredSemanticObject {
    pub semantic_id: ObjectId,
    pub store_key: StoreKey,
    pub created: bool,
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct RecoveryResult {
    pub scanned_orphans: u64,
    pub recovered_mappings: u64,
    pub corrupt_or_unreadable: u64,
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct FsckResult {
    pub mappings_checked: u64,
    pub healthy: u64,
    pub missing_objects: u64,
    pub corrupt_objects: u64,
    pub semantic_mismatches: u64,
    pub malformed_mappings: u64,
    pub orphan_store_objects: u64,
}

impl FsckResult {
    pub fn ok(&self) -> bool {
        self.missing_objects == 0
            && self.corrupt_objects == 0
            && self.semantic_mismatches == 0
            && self.malformed_mappings == 0
    }
}

pub struct AstraRepository {
    worktree: PathBuf,
    meta: PathBuf,
    mapping_root: PathBuf,
    store: LooseObjectStore,
}

impl AstraRepository {
    pub fn init(worktree: impl AsRef<Path>) -> Result<Self, RepositoryError> {
        let worktree = worktree.as_ref();
        fs::create_dir_all(worktree)?;
        let meta = worktree.join(".astra");
        match fs::create_dir(&meta) {
            Ok(()) => {}
            Err(err) if err.kind() == io::ErrorKind::AlreadyExists => return Err(RepositoryError::Exists),
            Err(err) => return Err(RepositoryError::Io(err)),
        }
let result = (|| {
            write_file_durable(&meta.join("format"), REPOSITORY_FORMAT, true)?;
            let mapping_root = meta.join("semantic-map");
            create_dir_all_durable(&mapping_root)?;
            let store = LooseObjectStore::open(meta.join("store"))?;
            sync_directory(&meta)?;
            sync_directory(worktree)?;
            Ok(Self { worktree: worktree.to_path_buf(), meta: meta.clone(), mapping_root, store })
        })();
        if result.is_err() {
            let _ = fs::remove_dir_all(&meta);
        }
        result
    }

    pub fn open(worktree: impl AsRef<Path>) -> Result<Self, RepositoryError> {
        let worktree = worktree.as_ref().to_path_buf();
        let meta = worktree.join(".astra");
        if !meta.is_dir() { return Err(RepositoryError::MissingMetadata); }
        let mut format = Vec::new();
        File::open(meta.join("format")).map_err(|_| RepositoryError::MissingMetadata)?.read_to_end(&mut format)?;
        if format != REPOSITORY_FORMAT { return Err(RepositoryError::UnsupportedFormat); }
        let mapping_root = meta.join("semantic-map");
        if !mapping_root.is_dir() { return Err(RepositoryError::MissingMetadata); }
        let store = LooseObjectStore::open(meta.join("store"))?;
        Ok(Self { worktree, meta, mapping_root, store })
    }

    pub fn worktree(&self) -> &Path { &self.worktree }
    pub fn metadata_root(&self) -> &Path { &self.meta }
    pub fn store(&self) -> &LooseObjectStore { &self.store }

    pub fn put(&self, value: &SemanticObject) -> Result<StoredSemanticObject, RepositoryError> {
        let envelope = encode_semantic(value)?;
        let semantic_id = value.semantic_id();
        let stored = self.store.put(&envelope)?;
        let mapping_created = self.publish_mapping(value.object_type(), semantic_id, stored.key)?;
        Ok(StoredSemanticObject {
            semantic_id,
            store_key: stored.key,
            created: stored.created || mapping_created,
        })
    }

    pub fn get(&self, object_type: ObjectType, semantic_id: ObjectId) -> Result<SemanticObject, RepositoryError> {
        let key = self.read_mapping(object_type, semantic_id)?;
        let envelope = self.store.get(key)?;
        if envelope.object_type != object_type { return Err(RepositoryError::WrongObjectType); }
        let value = decode_semantic(&envelope)?;
        if value.semantic_id() != semantic_id { return Err(RepositoryError::SemanticMismatch); }
        Ok(value)
    }

    fn mapping_path(&self, object_type: ObjectType, id: ObjectId) -> PathBuf {
        let kind = object_dir(object_type);
        let hex = id.to_hex();
        self.mapping_root.join(kind).join(&hex[..2]).join(&hex[2..])
    }

    fn publish_mapping(&self, object_type: ObjectType, id: ObjectId, key: StoreKey) -> Result<bool, RepositoryError> {
        let target = self.mapping_path(object_type, id);
        let parent = target.parent().expect("mapping path has parent");
        create_dir_all_durable(parent)?;
        let payload = format!("{}\n", key).into_bytes();
        if target.exists() {
            if fs::read(&target)? != payload { return Err(RepositoryError::MappingCollision); }
            return Ok(false);
        }
        let counter = UNIQUE_COUNTER.fetch_add(1, Ordering::Relaxed);
        let tmp = parent.join(format!(".{}.{}.{}.tmp", target.file_name().unwrap().to_string_lossy(), std::process::id(), counter));
        write_file_durable(&tmp, &payload, true)?;
        let result = match fs::hard_link(&tmp, &target) {
            Ok(()) => {
                sync_directory(parent)?;
                Ok(true)
            }
            Err(err) if err.kind() == io::ErrorKind::AlreadyExists => {
                if fs::read(&target)? != payload { Err(RepositoryError::MappingCollision) } else { Ok(false) }
            }
            Err(err) => Err(RepositoryError::Io(err)),
        };
        let _ = fs::remove_file(&tmp);
        result
    }

    fn read_mapping(&self, object_type: ObjectType, id: ObjectId) -> Result<StoreKey, RepositoryError> {
        let path = self.mapping_path(object_type, id);
        let bytes = match fs::read(path) {
            Ok(bytes) => bytes,
            Err(err) if err.kind() == io::ErrorKind::NotFound => return Err(RepositoryError::MissingSemanticObject(id)),
            Err(err) => return Err(RepositoryError::Io(err)),
        };
        if bytes.len() != 65 || bytes[64] != b'\n' { return Err(RepositoryError::MalformedMapping); }
        let text = std::str::from_utf8(&bytes[..64]).map_err(|_| RepositoryError::MalformedMapping)?;
        parse_store_key(text).ok_or(RepositoryError::MalformedMapping)
    }

    pub fn recover_orphan_mappings(&self) -> Result<RecoveryResult, RepositoryError> {
        let mut referenced = HashSet::new();
        for object_type in all_object_types() {
            let kind_root = self.mapping_root.join(object_dir(object_type));
            if !kind_root.exists() { continue; }
            for prefix in fs::read_dir(&kind_root)? {
                let prefix = prefix?;
                if !prefix.file_type()?.is_dir() { continue; }
                let prefix_name = prefix.file_name().to_string_lossy().into_owned();
                if !valid_lower_hex(&prefix_name, 2) { continue; }
                for entry in fs::read_dir(prefix.path())? {
                    let entry = entry?;
                    if !entry.file_type()?.is_file() { continue; }
                    let suffix = entry.file_name().to_string_lossy().into_owned();
                    let semantic_hex = format!("{prefix_name}{suffix}");
                    let Some(semantic_id) = parse_object_id(&semantic_hex) else { continue; };
                    if let Ok(key) = self.read_mapping(object_type, semantic_id) {
                        referenced.insert(key);
                    }
                }
            }
        }

        let mut result = RecoveryResult::default();
        for key in self.store.iter_keys()? {
            if referenced.contains(&key) { continue; }
            result.scanned_orphans += 1;
            let envelope = match self.store.get(key) {
                Ok(value) => value,
                Err(StoreError::NotFound(_)) | Err(StoreError::Corrupt { .. }) | Err(StoreError::Codec(_)) => {
                    result.corrupt_or_unreadable += 1;
                    continue;
                }
                Err(err) => return Err(RepositoryError::Store(err)),
            };
            let value = match decode_semantic(&envelope) {
                Ok(value) => value,
                Err(_) => {
                    result.corrupt_or_unreadable += 1;
                    continue;
                }
            };
            let semantic_id = value.semantic_id();
            self.publish_mapping(envelope.object_type, semantic_id, key)?;
            referenced.insert(key);
            result.recovered_mappings += 1;
        }
        Ok(result)
    }

    pub fn fsck(&self) -> Result<FsckResult, RepositoryError> {
        let mut result = FsckResult::default();
        let mut referenced = HashSet::new();

        for object_type in all_object_types() {
            let kind_root = self.mapping_root.join(object_dir(object_type));
            if !kind_root.exists() { continue; }
            for prefix in fs::read_dir(&kind_root)? {
                let prefix = prefix?;
                let prefix_name = prefix.file_name().to_string_lossy().into_owned();
                if !prefix.file_type()?.is_dir() || !valid_lower_hex(&prefix_name, 2) {
                    result.malformed_mappings += 1;
                    continue;
                }
                for entry in fs::read_dir(prefix.path())? {
                    let entry = entry?;
                    if !entry.file_type()?.is_file() {
                        result.malformed_mappings += 1;
                        continue;
                    }
                    let suffix = entry.file_name().to_string_lossy().into_owned();
                    let semantic_hex = format!("{prefix_name}{suffix}");
                    let Some(semantic_id) = parse_object_id(&semantic_hex) else {
                        result.malformed_mappings += 1;
                        continue;
                    };
                    result.mappings_checked += 1;
                    let key = match self.read_mapping(object_type, semantic_id) {
                        Ok(key) => key,
                        Err(RepositoryError::MalformedMapping) => {
                            result.malformed_mappings += 1;
                            continue;
                        }
                        Err(err) => return Err(err),
                    };
                    referenced.insert(key);
                    let envelope = match self.store.get(key) {
                        Ok(envelope) => envelope,
                        Err(StoreError::NotFound(_)) => {
                            result.missing_objects += 1;
                            continue;
                        }
                        Err(StoreError::Corrupt { .. }) | Err(StoreError::Codec(_)) => {
                            result.corrupt_objects += 1;
                            continue;
                        }
                        Err(err) => return Err(RepositoryError::Store(err)),
                    };
                    if envelope.object_type != object_type {
                        result.semantic_mismatches += 1;
                        continue;
                    }
                    match decode_semantic(&envelope) {
                        Ok(value) if value.semantic_id() == semantic_id => result.healthy += 1,
                        Ok(_) => result.semantic_mismatches += 1,
                        Err(_) => result.corrupt_objects += 1,
                    }
                }
            }
        }

        for entry in fs::read_dir(&self.mapping_root)? {
            let entry = entry?;
            let name = entry.file_name().to_string_lossy().into_owned();
            if !entry.file_type()?.is_dir() || !all_object_types().iter().any(|kind| object_dir(*kind) == name) {
                result.malformed_mappings += 1;
            }
        }

        let store_keys = self.store.iter_keys()?;
        result.orphan_store_objects = store_keys.into_iter().filter(|key| !referenced.contains(key)).count() as u64;
        Ok(result)
    }
}

fn all_object_types() -> [ObjectType; 9] {
    [
        ObjectType::Content,
        ObjectType::Tree,
        ObjectType::ChangeVersion,
        ObjectType::Revision,
        ObjectType::View,
        ObjectType::Operation,
        ObjectType::Conflict,
        ObjectType::Attestation,
        ObjectType::ReleaseManifest,
    ]
}

fn object_dir(value: ObjectType) -> &'static str {
    match value {
        ObjectType::Content => "content",
        ObjectType::Tree => "tree",
        ObjectType::ChangeVersion => "change-version",
        ObjectType::Revision => "revision",
        ObjectType::View => "view",
        ObjectType::Operation => "operation",
        ObjectType::Conflict => "conflict",
        ObjectType::Attestation => "attestation",
        ObjectType::ReleaseManifest => "release-manifest",
    }
}

fn valid_lower_hex(value: &str, len: usize) -> bool {
    value.len() == len && value.bytes().all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
}

fn parse_object_id(value: &str) -> Option<ObjectId> {
    if !valid_lower_hex(value, 64) { return None; }
    let mut out = [0_u8; 32];
    for (i, slot) in out.iter_mut().enumerate() {
        *slot = u8::from_str_radix(&value[i * 2..i * 2 + 2], 16).ok()?;
    }
    Some(ObjectId(out))
}

fn parse_store_key(value: &str) -> Option<StoreKey> { parse_object_id(value).map(StoreKey) }

fn write_file_durable(path: &Path, data: &[u8], exclusive: bool) -> Result<(), RepositoryError> {
    let mut options = OpenOptions::new();
    options.write(true).create(true);
    if exclusive { options.create_new(true); } else { options.truncate(true); }
    let mut file = options.open(path)?;
    file.write_all(data)?;
    file.sync_all()?;
    if let Some(parent) = path.parent() { sync_directory(parent)?; }
    Ok(())
}

fn create_dir_all_durable(path: &Path) -> Result<(), RepositoryError> {
    if path.is_dir() { return Ok(()); }
    let parent = path.parent().filter(|parent| *parent != path);
    if let Some(parent) = parent { create_dir_all_durable(parent)?; }
    match fs::create_dir(path) {
        Ok(()) => {}
        Err(err) if err.kind() == io::ErrorKind::AlreadyExists && path.is_dir() => {}
        Err(err) => return Err(RepositoryError::Io(err)),
    }
    sync_directory(path)?;
    if let Some(parent) = parent { sync_directory(parent)?; }
    Ok(())
}

#[cfg(unix)]
fn sync_directory(path: &Path) -> Result<(), RepositoryError> {
    File::open(path)?.sync_all()?;
    Ok(())
}

#[cfg(not(unix))]
fn sync_directory(_path: &Path) -> Result<(), RepositoryError> { Ok(()) }
