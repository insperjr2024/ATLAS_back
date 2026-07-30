class ResourceInUseError(Exception):
    """Levantada quando uma exclusão viola uma Foreign Key (registro ainda referenciado)."""
    pass


class RegraDeNegocioError(Exception):
    """Levantada quando uma regra de negócio é violada (dado tecnicamente válido, mas semanticamente errado)."""
    pass