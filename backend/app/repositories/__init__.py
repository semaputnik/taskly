"""
`app/crud.py` as a package: one module per cluster of aggregates, plus a
module of predicates shared across more than one of them.

This package holds no re-export surface of its own — `app/crud.py` is that
surface, importing every name the 35 call sites outside this package use, so
the split is invisible to them. Code inside this package reaches across its
own modules by importing their public names, same as any other caller; a
private helper never crosses a module boundary, which is what `predicates.py`
is for.
"""
