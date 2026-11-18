"""Industrial L2 business-data projection; no database, network or report renderer."""

from .diagnose import diagnose as diagnose, verify as verify
from .pack import load as load
from .pack import load_s2 as load_s2, IndustryPins as IndustryPins
