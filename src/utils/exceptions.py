class ResourceInUseError(Exception):
    """Levantada quando uma exclusão viola uma Foreign Key (registro ainda referenciado)."""
    pass