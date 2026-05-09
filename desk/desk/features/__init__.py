"""Features — sport-namespaced feature snapshots and the row builder.

`FeatureRow` is the sport-specific input the model consumes. Each sport
package ships its own subclass; this module's role is only to declare
the abstract handle the runner / replay use.
"""

from desk.features.types import FeatureRow  # noqa: F401
