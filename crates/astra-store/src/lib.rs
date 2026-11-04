//! Bootstrap durable loose-object store for AstraVCS.
//!
//! `StoreKey` is intentionally a physical bootstrap-storage identity for an
//! exact encoded [`ObjectEnvelope`]. It is not a semantic RevisionID/TreeID/etc.
//! and may be replaced by a later repository-format epoch without changing
//! semantic object identities.

use astra_model::{CodecError, ObjectEnvelope, ObjectId};
use std::fmt;
use std::fs::{self, File, OpenOptions};
use std::io::{self, Read, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};

pub const STORE_DOMAIN: &[u8] = b"ASTRA:LOOSE-OBJECT:V0";
const MAX_ENCODED_BYTES: u64 = astra_model::MAX_PAYLOAD_BYTES as u64 + 17;
static UNIQUE_COUNTER: AtomicU64 = AtomicU64::new(0);

#[derive(Clone, Copy, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub struct StoreKey(pub ObjectId);

impl StoreKey {
    pub fn from_encoded(encoded: &[u8]) -> Self {
        Self(ObjectId::digest(STORE_DOMAIN, &[encoded]))
    }

    pub fn to_hex(self) -> String {
        self.0.to_hex()
    }
}

impl fmt::Display for StoreKey {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}

#[derive(Debug)]
pub enum StoreError {
    Io(io::Error),
    Codec(CodecError),
    NotFound(StoreKey),
    Corrupt { key: StoreKey, reason: String },
    PublicationUnsupported(io::Error),
    UniquePathExhausted,
}

impl fmt::Display for StoreError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Io(err) => write!(f, "store I/O error: {err}"),
            Self::Codec(err) => write!(f, "stored envelope is invalid: {err}"),
            Self::NotFound(key) => write!(f, "object not found: {key}"),
            Self::Corrupt { key, reason } => write!(f, "corrupt object {key}: {reason}"),
            Self::PublicationUnsupported(err) => write!(
                f,
                "bootstrap loose store requires same-filesystem hard-link publication: {err}"
            ),
            Self::UniquePathExhausted => write!(f, "unable to allocate unique bootstrap store path"),
        }
    }
}

impl std::error::Error for StoreError {}

impl From<io::Error> for StoreError {
    fn from(value: io::Error) -> Self {
        Self::Io(value)
    }
}

impl From<CodecError> for StoreError {
    fn from(value: CodecError) -> Self {
        Self::Codec(value)
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct PutResult {
    pub key: StoreKey,
    pub created: bool,
    pub repaired_corruption: bool,
}

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct ScrubResult {
    pub checked: u64,
    pub healthy: u64,
    pub quarantined: u64,
}

pub struct LooseObjectStore {
    root: PathBuf,
    objects: PathBuf,
    quarantine: PathBuf,
    tmp: PathBuf,
}

impl LooseObjectStore {
    pub fn open(root: impl AsRef<Path>) -> Result<Self, StoreError> {
        let root = root.as_ref().to_path_buf();
        let objects = root.join("objects").join("sha256");
        let quarantine = root.join("quarantine");
        let tmp = root.join("tmp");
        create_dir_all_durable(&objects)?;
        create_dir_all_durable(&quarantine)?;
        create_dir_all_durable(&tmp)?;
        Ok(Self {
            root,
            objects,
            quarantine,
            tmp,
        })
    }

    pub fn root(&self) -> &Path {
        &self.root
    }

    pub fn object_path(&self, key: StoreKey) -> PathBuf {
        let hex = key.to_hex();
        self.objects.join(&hex[..2]).join(&hex[2..])
    }

    fn unique_path(&self, directory: &Path, key: StoreKey, suffix: &str) -> Result<PathBuf, StoreError> {
        create_dir_all_durable(directory)?;
        for _ in 0..1024 {
            let counter = UNIQUE_COUNTER.fetch_add(1, Ordering::Relaxed);
            let name = format!("{}.{}.{}{}", key, std::process::id(), counter, suffix);
            let candidate = directory.join(name);
            if !candidate.exists() {
                return Ok(candidate);
            }
        }
        Err(StoreError::UniquePathExhausted)
    }

    fn write_temp(&self, encoded: &[u8], key: StoreKey) -> Result<PathBuf, StoreError> {
        let temp = self.unique_path(&self.tmp, key, ".tmp")?;
        let mut file = OpenOptions::new()
            .create_new(true)
            .write(true)
            .open(&temp)?;
        file.write_all(encoded)?;
        file.sync_all()?;
        Ok(temp)
    }

    fn read_exact(&self, path: &Path, key: StoreKey) -> Result<Vec<u8>, StoreError> {
        let metadata = match fs::metadata(path) {
            Ok(metadata) => metadata,
            Err(err) if err.kind() == io::ErrorKind::NotFound => return Err(StoreError::NotFound(key)),
            Err(err) => return Err(StoreError::Io(err)),
        };
        if metadata.len() > MAX_ENCODED_BYTES {
            return Err(StoreError::Corrupt {
                key,
                reason: "stored object exceeds bootstrap envelope size limit".into(),
            });
        }
        let mut file = File::open(path)?;
        let mut bytes = Vec::with_capacity(metadata.len() as usize);
        file.read_to_end(&mut bytes)?;
        Ok(bytes)
    }

    fn verify_bytes(&self, key: StoreKey, encoded: &[u8]) -> Result<ObjectEnvelope, StoreError> {
        if StoreKey::from_encoded(encoded) != key {
            return Err(StoreError::Corrupt {
                key,
                reason: "stored bytes do not match StoreKey".into(),
            });
        }
        ObjectEnvelope::decode(encoded).map_err(|err| StoreError::Corrupt {
            key,
            reason: format!("invalid bootstrap envelope: {err}"),
        })
    }

    fn quarantine_path(&self, path: &Path, key: StoreKey) -> Result<PathBuf, StoreError> {
        let destination = self.unique_path(&self.quarantine, key, ".bad")?;
        match fs::rename(path, &destination) {
            Ok(()) => {
                if let Some(parent) = path.parent() {
                    sync_directory(parent)?;
                }
                sync_directory(&self.quarantine)?;
                Ok(destination)
            }
            Err(err) if err.kind() == io::ErrorKind::NotFound => Ok(destination),
            Err(err) => Err(StoreError::Io(err)),
        }
    }

    pub fn put(&self, envelope: &ObjectEnvelope) -> Result<PutResult, StoreError> {
        let encoded = envelope.encode()?;
        let key = StoreKey::from_encoded(&encoded);
        let target = self.object_path(key);
        let parent = target.parent().expect("object path always has parent");
        create_dir_all_durable(parent)?;

        let mut repaired = false;
        while target.exists() {
            match self.read_exact(&target, key).and_then(|bytes| {
                self.verify_bytes(key, &bytes)?;
                if bytes != encoded {
                    return Err(StoreError::Corrupt {
                        key,
                        reason: "StoreKey collision with different valid bytes".into(),
                    });
                }
                Ok(())
            }) {
                Ok(()) => {
                    return Ok(PutResult {
                        key,
                        created: false,
                        repaired_corruption: repaired,
                    });
                }
                Err(StoreError::Corrupt { .. }) | Err(StoreError::NotFound(_)) => {
                    self.quarantine_path(&target, key)?;
                    repaired = true;
                }
                Err(err) => return Err(err),
            }
        }

        let temp = self.write_temp(&encoded, key)?;
        let publish_result = fs::hard_link(&temp, &target);
        let result = match publish_result {
            Ok(()) => {
                sync_directory(parent)?;
                Ok(PutResult {
                    key,
                    created: true,
                    repaired_corruption: repaired,
                })
            }
            Err(err) if err.kind() == io::ErrorKind::AlreadyExists => {
                let bytes = self.read_exact(&target, key)?;
                self.verify_bytes(key, &bytes)?;
                if bytes != encoded {
                    Err(StoreError::Corrupt {
                        key,
                        reason: "concurrent StoreKey collision".into(),
                    })
                } else {
                    Ok(PutResult {
                        key,
                        created: false,
                        repaired_corruption: repaired,
                    })
                }
            }
            Err(err)
                if matches!(
                    err.raw_os_error(),
                    Some(1) | Some(18) | Some(95)
                ) => Err(StoreError::PublicationUnsupported(err)),
            Err(err) => Err(StoreError::Io(err)),
        };
        let _ = fs::remove_file(&temp);
        result
    }

    pub fn get(&self, key: StoreKey) -> Result<ObjectEnvelope, StoreError> {
        let path = self.object_path(key);
        let encoded = self.read_exact(&path, key)?;
        self.verify_bytes(key, &encoded)
    }

    pub fn get_encoded(&self, key: StoreKey) -> Result<Vec<u8>, StoreError> {
        let path = self.object_path(key);
        let encoded = self.read_exact(&path, key)?;
        self.verify_bytes(key, &encoded)?;
        Ok(encoded)
    }

    pub fn contains(&self, key: StoreKey) -> Result<bool, StoreError> {
        match self.get(key) {
            Ok(_) => Ok(true),
            Err(StoreError::NotFound(_)) => Ok(false),
            Err(err) => Err(err),
        }
    }

    pub fn iter_keys(&self) -> Result<Vec<StoreKey>, StoreError> {
        let mut keys = Vec::new();
        for prefix_entry in fs::read_dir(&self.objects)? {
            let prefix_entry = prefix_entry?;
            if !prefix_entry.file_type()?.is_dir() {
                continue;
            }
            let prefix = prefix_entry.file_name().to_string_lossy().into_owned();
            if prefix.len() != 2 || !prefix.bytes().all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase()) {
                continue;
            }
            for object_entry in fs::read_dir(prefix_entry.path())? {
                let object_entry = object_entry?;
                if !object_entry.file_type()?.is_file() {
                    continue;
                }
                let suffix = object_entry.file_name().to_string_lossy().into_owned();
                let hex = format!("{prefix}{suffix}");
                if let Some(key) = parse_store_key(&hex) {
                    keys.push(key);
                }
            }
        }
        keys.sort_unstable();
        Ok(keys)
    }

    pub fn scrub(&self, quarantine_corrupt: bool) -> Result<ScrubResult, StoreError> {
        let mut result = ScrubResult::default();
        for key in self.iter_keys()? {
            result.checked += 1;
            let path = self.object_path(key);
            match self.read_exact(&path, key).and_then(|bytes| self.verify_bytes(key, &bytes).map(|_| ())) {
                Ok(()) => result.healthy += 1,
                Err(StoreError::Corrupt { .. }) | Err(StoreError::NotFound(_)) => {
                    if quarantine_corrupt && path.exists() {
                        self.quarantine_path(&path, key)?;
                        result.quarantined += 1;
                    }
                }
                Err(err) => return Err(err),
            }
        }
        Ok(result)
    }

    pub fn cleanup_temps(&self) -> Result<u64, StoreError> {
        let mut removed = 0;
        for entry in fs::read_dir(&self.tmp)? {
            let entry = entry?;
            if entry.file_type()?.is_file()
                && entry.file_name().to_string_lossy().ends_with(".tmp")
            {
                fs::remove_file(entry.path())?;
                removed += 1;
            }
        }
        sync_directory(&self.tmp)?;
        Ok(removed)
    }
}


fn create_dir_all_durable(path: &Path) -> Result<(), StoreError> {
    if path.is_dir() {
        return Ok(());
    }
    let parent = path.parent().filter(|parent| *parent != path);
    if let Some(parent) = parent {
        create_dir_all_durable(parent)?;
    }
    match fs::create_dir(path) {
        Ok(()) => {}
        Err(err) if err.kind() == io::ErrorKind::AlreadyExists && path.is_dir() => {}
        Err(err) => return Err(StoreError::Io(err)),
    }
    sync_directory(path)?;
    if let Some(parent) = parent {
        sync_directory(parent)?;
    }
    Ok(())
}

fn parse_store_key(hex: &str) -> Option<StoreKey> {
    if hex.len() != 64 || !hex.bytes().all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase()) {
        return None;
    }
    let mut bytes = [0_u8; 32];
    for (index, slot) in bytes.iter_mut().enumerate() {
        *slot = u8::from_str_radix(&hex[index * 2..index * 2 + 2], 16).ok()?;
    }
    Some(StoreKey(ObjectId(bytes)))
}

#[cfg(unix)]
fn sync_directory(path: &Path) -> Result<(), StoreError> {
    File::open(path)?.sync_all()?;
    Ok(())
}

#[cfg(not(unix))]
fn sync_directory(_path: &Path) -> Result<(), StoreError> {
    // Windows durability guarantee is not provided by this bootstrap store
    // implementation. The current Rust implementation explicitly does not claim
    // directory-level fsync or flush durability on Windows (RFC-6.12). A
    // platform-specific implementation using Windows directory handles and
    // fsync-style semantics would be required to provide that guarantee.
    // Until then, the store does not provide directory durability guarantees
    // on Windows, and publication on Windows relies on the underlying
    // filesystem's default durability characteristics.
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use astra_model::ObjectType;
    use std::time::{SystemTime, UNIX_EPOCH};

    struct TempDir(PathBuf);

    impl TempDir {
        fn new() -> Self {
            let nonce = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos();
            let path = std::env::temp_dir().join(format!(
                "astravcs-store-test-{}-{nonce}",
                std::process::id()
            ));
            fs::create_dir_all(&path).unwrap();
            Self(path)
        }
    }

    impl Drop for TempDir {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    fn envelope(payload: &[u8]) -> ObjectEnvelope {
        ObjectEnvelope::new(ObjectType::Content, payload.to_vec())
    }

    #[test]
    fn put_get_and_duplicate_are_exact() {
        let temp = TempDir::new();
        let store = LooseObjectStore::open(&temp.0).unwrap();
        let object = envelope(b"hello");
        let first = store.put(&object).unwrap();
        assert!(first.created);
        assert_eq!(store.get(first.key).unwrap(), object);
        let second = store.put(&object).unwrap();
        assert!(!second.created);
        assert_eq!(first.key, second.key);
    }

    #[test]
    fn concurrent_duplicate_writers_converge() {
        use std::sync::Arc;
        use std::thread;

        let temp = TempDir::new();
        let store = Arc::new(LooseObjectStore::open(&temp.0).unwrap());
        let mut handles = Vec::new();
        for _ in 0..16 {
            let store = Arc::clone(&store);
            handles.push(thread::spawn(move || store.put(&envelope(b"same")).unwrap()));
        }
        let results: Vec<_> = handles.into_iter().map(|handle| handle.join().unwrap()).collect();
        assert_eq!(results.iter().filter(|result| result.created).count(), 1);
        let first_key = results[0].key;
        assert!(results.iter().all(|result| result.key == first_key));
        assert_eq!(store.iter_keys().unwrap(), vec![first_key]);
    }

    #[test]
    fn scrub_quarantines_corruption() {
        let temp = TempDir::new();
        let store = LooseObjectStore::open(&temp.0).unwrap();
        let result = store.put(&envelope(b"data")).unwrap();
        fs::write(store.object_path(result.key), b"corrupt").unwrap();
        let scrub = store.scrub(true).unwrap();
        assert_eq!(scrub.checked, 1);
        assert_eq!(scrub.healthy, 0);
        assert_eq!(scrub.quarantined, 1);
        assert!(!store.object_path(result.key).exists());
    }

    fn expected_vector(name: &str) -> &'static str {
        include_str!("../../../tests/vectors/store-v0.tsv")
            .lines()
            .filter(|line| !line.is_empty() && !line.starts_with('#'))
            .find_map(|line| {
                let (key, value) = line.split_once('\t')?;
                (key == name).then_some(value)
            })
            .unwrap_or_else(|| panic!("missing store vector: {name}"))
    }

    #[test]
    fn bootstrap_store_keys_match_vectors() {
        assert_eq!(
            StoreKey::from_encoded(&envelope(b"").encode().unwrap()).to_hex(),
            expected_vector("content.empty")
        );
        assert_eq!(
            StoreKey::from_encoded(&envelope(b"hello").encode().unwrap()).to_hex(),
            expected_vector("content.hello")
        );
        assert_eq!(
            StoreKey::from_encoded(
                &ObjectEnvelope::new(ObjectType::Tree, b"payload".to_vec())
                    .encode()
                    .unwrap()
            )
            .to_hex(),
            expected_vector("tree.payload")
        );
        assert_eq!(
            StoreKey::from_encoded(
                &ObjectEnvelope::new(ObjectType::Conflict, (0_u8..16).collect())
                    .encode()
                    .unwrap()
            )
            .to_hex(),
            expected_vector("conflict.binary")
        );
    }

    #[test]
    fn key_changes_with_type_and_payload() {
        let content = envelope(b"x").encode().unwrap();
        let tree = ObjectEnvelope::new(ObjectType::Tree, b"x".to_vec())
            .encode()
            .unwrap();
        assert_ne!(StoreKey::from_encoded(&content), StoreKey::from_encoded(&tree));
        assert_ne!(
            StoreKey::from_encoded(&content),
            StoreKey::from_encoded(&envelope(b"y").encode().unwrap())
        );
    }
}
