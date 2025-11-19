"""
Utilities for freezing OpenType features using FontFreeze logic.

Portions of this module are adapted from FontFreeze
(https://github.com/MuTsunTsai/fontfreeze) and retain the original MIT License.
"""

from __future__ import annotations

from typing import Iterable, Sequence

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.otTables import (
    FeatureParamsCharacterVariants,
    FeatureParamsStylisticSet,
    featureParamTypes,
)

hideRemovedFeature = True


def clearFeatureRecord(featureRecord) -> None:
    featureRecord.Feature.LookupListIndex.clear()
    featureRecord.Feature.LookupCount = 0
    if hideRemovedFeature:
        featureRecord.FeatureTag = "DELT"


class Activator:
    def __init__(self, font: TTFont, args: dict) -> None:
        self.font = font
        self.features = args.get("features") or []
        options: dict = args.get("options") or {}
        self.target = options.get("target")
        self.singleSub = options.get("singleSub")
        self.singleSubs: dict[str, str] = {}

        if len(self.features) == 0 or "GSUB" not in self.font:
            return

        self.cmapTables = self.font["cmap"].tables
        self.unicodeGlyphs = {name for table in self.cmapTables for name in table.cmap.values()}

        gsub_table = self.font["GSUB"].table
        self.featureRecords = gsub_table.FeatureList.FeatureRecord
        self.lookup = gsub_table.LookupList.Lookup

        scriptRecords = gsub_table.ScriptList.ScriptRecord
        for scriptRecord in scriptRecords:
            self.activateInScript(scriptRecord.Script)

        if self.singleSub:
            self.applySingleSubstitutions()

    def activateInScript(self, script) -> None:
        if script.DefaultLangSys is not None:
            self.activateInLangSys(script.DefaultLangSys)
        for langSysRecord in script.LangSysRecord:
            self.activateInLangSys(langSysRecord.LangSys)

    def activateInLangSys(self, langSys) -> None:
        targetRecord = None

        # try to find existing target feature
        for index in langSys.FeatureIndex:
            featureRecord = self.featureRecords[index]
            if featureRecord.FeatureTag == self.target:
                targetRecord = featureRecord

        for index in langSys.FeatureIndex:
            featureRecord = self.featureRecords[index]
            if featureRecord.FeatureTag in self.features:
                if self.singleSub:
                    self.findSingleSubstitution(featureRecord)

                if targetRecord is None:
                    # if there's no existing one, use the first matching feature as target
                    targetRecord = featureRecord
                    featureParamTypes[self.target] = (
                        FeatureParamsStylisticSet
                        if featureRecord.FeatureTag.startswith("ss")
                        else FeatureParamsCharacterVariants
                    )
                    featureRecord.FeatureTag = self.target
                else:
                    Activator.moveFeatureLookups(featureRecord.Feature, targetRecord.Feature)
                    clearFeatureRecord(featureRecord)

        if targetRecord is not None:
            targetRecord.Feature.LookupListIndex.sort()

    def findSingleSubstitution(self, featureRecord) -> None:
        for lookupIndex in featureRecord.Feature.LookupListIndex:
            lookup = self.lookup[lookupIndex]
            if lookup.LookupType == 1:  # Single substitution
                subTables = lookup.SubTable
                for sub in subTables:
                    for key, value in sub.mapping.items():
                        self.singleSubs[key] = value
            elif lookup.LookupType == 2:  # Multiple substitution (one-to-many)
                for sub in lookup.SubTable:
                    for key, value_list in sub.mapping.items():
                        # Only handle single-element lists as single substitutions
                        if len(value_list) == 1:
                            self.singleSubs[key] = value_list[0]
            elif lookup.LookupType == 7:  # Extension lookup
                for sub in lookup.SubTable:
                    ext = sub.ExtSubTable
                    if ext.LookupType == 1:
                        for key, value in ext.mapping.items():
                            self.singleSubs[key] = value
                    elif ext.LookupType == 2:
                        for key, value_list in ext.mapping.items():
                            if len(value_list) == 1:
                                self.singleSubs[key] = value_list[0]

    def applySingleSubstitutions(self) -> None:
        if not self.singleSubs:
            return

        cache: dict[str, str] = {}

        def resolve(glyph: str) -> str:
            if glyph in cache:
                return cache[glyph]
            seen = set()
            current = glyph
            while current in self.singleSubs and current not in seen:
                seen.add(current)
                current = self.singleSubs[current]
            cache[glyph] = current
            return current

        for table in self.cmapTables:
            for index, glyph in table.cmap.items():
                table.cmap[index] = resolve(glyph)

    @staticmethod
    def moveFeatureLookups(fromFeature, toFeature) -> None:
        toFeature.LookupListIndex.extend(fromFeature.LookupListIndex)
        toFeature.LookupCount += fromFeature.LookupCount


def freeze_features(
    input_path: str,
    features: Sequence[str] | Iterable[str],
    output_path: str | None = None,
    *,
    target_feature: str = "calt",
    single_sub: bool = True,
) -> None:
    """
    Freeze the requested features by moving their lookups into the target feature.
    """
    feature_list = list(features)
    if not feature_list:
        return

    if output_path is None:
        output_path = input_path

    def _apply(hide_removed: bool) -> TTFont:
        global hideRemovedFeature
        hideRemovedFeature = hide_removed
        font = TTFont(input_path)
        Activator(
            font,
            {
                "features": feature_list,
                "options": {
                    "target": target_feature,
                    "singleSub": single_sub,
                },
            },
        )
        return font

    font = _apply(True)
    try:
        font.save(output_path)
    except AssertionError as exc:
        if "DELT" not in str(exc):
            raise
        font = _apply(False)
        font.save(output_path)
