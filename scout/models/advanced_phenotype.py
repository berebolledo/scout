# -*- coding: utf-8 -*-


class PhenoPanel(dict):
    """Represents an advanced phenotyping object. Can contain sub-panels objects
    _id = str # created by this class
    institute = str # required
    name = str
    description = str
    subpanels = []
    """

    def __init__(self, id, institute, name, description):
        self["_id"] = (id,)
        self["institute"] = institute
        self["name"] = name
        self["description"] = description
        self["subpanels"] = subpanels()

    def subpanels():
        return None
