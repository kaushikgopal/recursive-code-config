"""
    A script to generate Recursive fonts for code with Regular, Italic, Bold, & Bold Italic,
    as configured in config.yaml. See Readme for usage instructions.

    Run from the directory above, pointing to a config and a variable font path, e.g.

    python3 scripts/instantiate-code-fonts.py <premade-configs/casual.yaml>
"""

import os
import pathlib
import glob
from fontTools import ttLib
import subprocess
import shutil
import yaml
import sys
import ttfautohint
from fontTools.varLib import instancer
from fontTools.varLib.instancer import OverlapMode
from fontTools.varLib.instancer.featureVars import instantiateFeatureVariations
from dlig2calt import dlig2calt
from mergePowerlineFont import mergePowerlineFont
from ttfautohint.options import USER_OPTIONS as ttfautohint_options
from fontfreeze_activation import freeze_features
from borrow_glyphs import borrow_glyphs
from join_dashes import join_dashes
from add_characters import add_characters
from add_stylistic_set import add_stylistic_set
from long_arrows import long_arrows

# if you provide a custom config path, this picks it up
try:
    configPath = sys.argv[1]
except IndexError:
    configPath = './config.yaml'

# gets font path passed in
try:
    fontPath = sys.argv[2] # allows custom path to be passed in, helpful for generating new release from arrowtype/recursive dir
except IndexError:
    fontPath =  glob.glob('./font-data/Recursive_VF_*.ttf')[0] # allows script to run without font path passed in.

# read yaml config
with open(configPath, encoding='utf-8') as file:
    fontOptions = yaml.load(file, Loader=yaml.FullLoader)

# GET / SET NAME HELPER FUNCTIONS

def getFontNameID(font, ID, platformID=3, platEncID=1):
    name = str(font["name"].getName(ID, platformID, platEncID))
    return name


def setFontNameID(font, ID, newName):

    print(f"\n\t• name {ID}:")
    macIDs = {"platformID": 3, "platEncID": 1, "langID": 0x409}
    winIDs = {"platformID": 1, "platEncID": 0, "langID": 0x0}

    oldMacName = font["name"].getName(ID, *macIDs.values())
    oldWinName = font["name"].getName(ID, *winIDs.values())

    if oldMacName != newName:
        print(f"\t\t Mac name was '{oldMacName}'")
        font["name"].setName(newName, ID, *macIDs.values())
        print(f"\t\t Mac name now '{newName}'")

    if oldWinName != newName:
        print(f"\t\t Win name was '{oldWinName}'")
        font["name"].setName(newName, ID, *winIDs.values())
        print(f"\t\t Win name now '{newName}'")


# ----------------------------------------------
# MAIN FUNCTION

# The string to find in the source (Recursive) name records. Moxy rebrands the
# family to the config's "Family Name" directly (no "Recursive" prefix). Spaces in
# the family name become hyphens in the folder and file names, e.g.
# "Moxy Static" -> family "Moxy Static", folder "fonts/Moxy-Static",
# files "Moxy-Static-<Style>-<ver>.ttf". (The PostScript name strips the spaces.)
oldName = "Recursive"

# OFL-1.1 license metadata baked into the name table (id 0/13/14). Moxy derives
# from Recursive + Lilex (both OFL-1.1), so the font stays OFL-1.1; "Moxy" is a
# Reserved Font Name. See OFL.txt.
COPYRIGHT = (
    'Copyright 2026 Kaushik Gopal (https://github.com/kaushikgopal/font-moxy), '
    'with Reserved Font Name "Moxy". Portions copyright 2019 The Recursive Project '
    'Authors; portions copyright 2019 The Lilex Project Authors.'
)
LICENSE_DESC = (
    "This Font Software is licensed under the SIL Open Font License, Version 1.1. "
    "This license is available with a FAQ at https://openfontlicense.org"
)
LICENSE_URL = "https://openfontlicense.org"

def splitFont(
        # Folder mirrors the family name, spaces -> hyphens:
        #   "Moxy Static" -> "Moxy-Static", "Moxy X123" -> "Moxy-X123".
        outputDirectory=fontOptions['Family Name'].replace(" ", "-"),
):

    # access font as TTFont object
    varfont = ttLib.TTFont(fontPath)
    if "ss08" in fontOptions.get("Features", []):
        from glyph_tweaks import add_shortened_c_alternate
        print("\n\t• Added shortened-terminal C alternate to ss08")
        add_shortened_c_alternate(varfont)

    fontFileName = os.path.basename(fontPath)


    outputSubDir = f"fonts/{outputDirectory}"

    for instance in fontOptions["Fonts"]:

        print("\n--------------------------------------------------------------------------------------\n" + instance)

        axisLocation = {
            "wght": fontOptions["Fonts"][instance]["wght"],
            "CASL": fontOptions["Fonts"][instance]["CASL"],
            "MONO": fontOptions["Fonts"][instance]["MONO"],
            "slnt": fontOptions["Fonts"][instance]["slnt"],
            "CRSV": fontOptions["Fonts"][instance]["CRSV"],
        }

        instanceFont = instancer.instantiateVariableFont(
            varfont,
            axisLocation,
            overlap=OverlapMode.REMOVE
        )

        instantiateFeatureVariations(instanceFont, axisLocation)

        # UPDATE NAME ID 6, postscript name
        currentPsName = getFontNameID(instanceFont, 6)
        newPsName = (currentPsName\
            .replace("Sans", "")\
            .replace(oldName, fontOptions['Family Name'].replace(" ",""))\
            .replace("LinearLight", instance.replace(" ", "")))
        setFontNameID(instanceFont, 6, newPsName)

        # UPDATE NAME ID 4, full font name
        currentFullName = getFontNameID(instanceFont, 4)
        newFullName = (currentFullName\
            .replace("Sans", "")\
            .replace(oldName, fontOptions['Family Name'])\
            .replace(" Linear Light", instance))\
            .replace(" Regular", "")
        setFontNameID(instanceFont, 4, newFullName)

        # UPDATE NAME ID 3, unique font ID
        currentUniqueName = getFontNameID(instanceFont, 3)
        newUniqueName = (currentUniqueName.replace(currentPsName, newPsName))
        setFontNameID(instanceFont, 3, newUniqueName)

        # ADD name 2, style linking name
        newStyleLinkingName = instance
        setFontNameID(instanceFont, 2, newStyleLinkingName)
        setFontNameID(instanceFont, 17, newStyleLinkingName)

        # UPDATE NAME ID 1, Font Family name
        currentFamName = getFontNameID(instanceFont, 1)
        newFamName = (newFullName.replace(f" {instance}", ""))
        setFontNameID(instanceFont, 1, newFamName)
        setFontNameID(instanceFont, 16, newFamName)

        # License metadata: OFL-1.1 + Reserved Font Name "Moxy" (see OFL.txt)
        setFontNameID(instanceFont, 0, COPYRIGHT)
        setFontNameID(instanceFont, 13, LICENSE_DESC)
        setFontNameID(instanceFont, 14, LICENSE_URL)

        # Filename mirrors the family name with spaces -> hyphens (like the folder),
        # while the style stays a single token, e.g. "Moxy Static" + "Bold Italic"
        # -> "Moxy-Static-BoldItalic-<ver>.ttf". (NameID 6 / PostScript name above
        # strips spaces instead, since PostScript names may not contain spaces.)
        newFileName = fontFileName\
            .replace(oldName, fontOptions['Family Name'].replace(" ", "-"))\
            .replace("_VF_", "-" + instance.replace(" ", "") + "-")

        # make dir for new fonts
        pathlib.Path(outputSubDir).mkdir(parents=True, exist_ok=True)

        # -------------------------------------------------------
        # save instance font

        outputPath = f"{outputSubDir}/{newFileName}"

        # save font
        instanceFont.save(outputPath)

        # -------------------------------------------------------
        # Code font special stuff in post processing

        # Freeze rvrn and stylistic set features
        # Note: ss04 and similar features use Type 2 (Multiple Substitution) lookups
        features_to_freeze = ["rvrn"] + fontOptions["Features"]
        freeze_features(
            outputPath,
            features_to_freeze,
            target_feature="calt",
            single_sub=True,
        )

        if fontOptions['Code Ligatures']:
            # swap dlig2calt to make code ligatures work in old code editor apps
            dlig2calt(outputPath, inplace=True)

        # if casual, merge with casual PL; if linear merge w/ Linear PL
        if fontOptions["Fonts"][instance]["CASL"] > 0.5:
            mergePowerlineFont(outputPath, "./font-data/NerdfontsPL-Regular Casual.ttf")
        else:
            mergePowerlineFont(outputPath, "./font-data/NerdfontsPL-Regular Linear.ttf")

        # TODO, maybe: make VF for powerline font, then instantiate specific CASL instance before merging

        # -------------------------------------------------------
        # OpenType Table fixes

        monoFont =  ttLib.TTFont(outputPath)

        # -------------------------------------------------------
        # Borrow glyph outlines from other open-source fonts.
        #
        # Some glyphs simply don't exist anywhere in the Recursive variable font,
        # so they can't be frozen on like the ssXX stylistic sets. The canonical
        # example is Lilex's cv13 "curvier parentheses". We graft the actual
        # outlines in here, weight-matched and slant-matched to this instance.
        # (Borrowed fonts must be OFL-compatible and credited; see font-data/.)
        borrowSpecs = fontOptions.get("Borrowed Glyphs") or []
        for spec in borrowSpecs:
            sourcePath = spec["source"]
            result = borrow_glyphs(
                monoFont,
                source_path=sourcePath,
                glyph_map=spec["glyphs"],
                slant=fontOptions["Fonts"][instance]["slnt"],
                probe=spec.get("probe"),
                max_stroke_mismatch=spec.get("max_stroke_mismatch", 0.12),
                align=spec.get("align"),
            )
            srcName = os.path.basename(sourcePath)
            if result["replaced"]:
                print(
                    f"\n\t• Borrowed {result['replaced']} from {srcName} "
                    f"(target stroke {result['target_stroke']:.0f}, "
                    f"matched source wght {result['matched_wght']} "
                    f"@ stroke {result['source_stroke']:.0f})"
                )
            elif result["skipped"]:
                print(
                    f"\n\t• Kept native glyphs {result['skipped']} "
                    f"(skipped {srcName}: best match {result['mismatch'] * 100:.0f}% "
                    f"off target stroke, over threshold)"
                )

        # -------------------------------------------------------
        # Join hyphen runs into a continuous line, Lilex-style (--- and longer).
        joinCfg = fontOptions.get("Join Dashes")
        if joinCfg:
            jres = join_dashes(
                monoFont,
                source_path=joinCfg["source"],
                slant=fontOptions["Fonts"][instance]["slnt"],
                max_stroke_mismatch=joinCfg.get("max_stroke_mismatch", 0.18),
            )
            if jres["done"]:
                print(
                    f"\n\t• Joined hyphen runs (---, ----, …) from "
                    f"{os.path.basename(joinCfg['source'])} "
                    f"(matched source wght {jres['matched_wght']})"
                )
                # Long arrows of arbitrary length, Recursive-style, built on the
                # connected-dash shaft (--->, <--, <---, longer; both directions).
                long_arrows(monoFont, recursive_vf_path=fontPath, axis_location=axisLocation)
                print("\t• Added Recursive-style long arrows (--->, <--, …, any length)")
            else:
                print(f"\n\t• Kept native dashes ({jres['reason']})")

        # -------------------------------------------------------
        # Add brand-new characters Recursive lacks (e.g. Lilex's fancy
        # single-character arrows), with cmap entries.
        addCfg = fontOptions.get("Add Characters")
        if addCfg:
            ares = add_characters(
                monoFont,
                source_path=addCfg["source"],
                glyph_names=addCfg["glyphs"],
                slant=fontOptions["Fonts"][instance]["slnt"],
            )
            print(
                f"\n\t• Added {len(ares['added'])} characters from "
                f"{os.path.basename(addCfg['source'])} "
                f"(matched source wght {ares['matched_wght']})"
            )

        # -------------------------------------------------------
        # Optional stylistic sets (e.g. Lilex's thin backslash, toggleable).
        for ssCfg in fontOptions.get("Stylistic Sets") or []:
            sres = add_stylistic_set(
                monoFont,
                source_path=ssCfg["source"],
                feature_tag=ssCfg["feature"],
                ui_name=ssCfg["name"],
                glyph_map=ssCfg["glyphs"],
                slant=fontOptions["Fonts"][instance]["slnt"],
                escape_only=ssCfg.get("escape_only", False),
            )
            print(
                f"\n\t• Added optional '{sres['feature']}' ({ssCfg['name']}) "
                f"from {os.path.basename(ssCfg['source'])}"
            )

        # -------------------------------------------------------
        # %, /, \, ✓, •, $, @, & all drawn directly (OFL-clean geometry) —
        # no external outline is read or shipped. All weight- and slant-matched
        # to this instance — the same shapes the variable-font build uses.
        # Composites (backslash.code, .case, escape ligatures, bullet.case,
        # uni2219, at.case) reference these as components, so they inherit.
        from glyph_tweaks import (
            draw_percent_static, draw_slash_static, draw_backslash_static,
            draw_checkmark_static, draw_bullet_static, draw_dollar_static,
            draw_at_static, draw_ampersand_static, draw_two_static,
            draw_four_static, draw_five_static, draw_seven_static,
        )
        inst_wght = fontOptions["Fonts"][instance]["wght"]
        inst_slnt = fontOptions["Fonts"][instance]["slnt"]
        draw_percent_static(monoFont, inst_wght, inst_slnt)
        draw_slash_static(monoFont, inst_wght, inst_slnt)
        draw_backslash_static(monoFont, inst_wght, inst_slnt)
        draw_checkmark_static(monoFont, inst_wght, inst_slnt)
        draw_bullet_static(monoFont, inst_wght, inst_slnt)
        draw_dollar_static(monoFont, inst_wght, inst_slnt)
        draw_at_static(monoFont, inst_wght, inst_slnt)
        draw_ampersand_static(monoFont, inst_wght, inst_slnt)
        draw_two_static(monoFont, inst_wght, inst_slnt)
        draw_four_static(monoFont, inst_wght, inst_slnt)
        draw_five_static(monoFont, inst_wght, inst_slnt)
        draw_seven_static(monoFont, inst_wght, inst_slnt)
        print(f"\n\t• Drew %, /, \\, ✓, •, $, @, &, 2, 4, 5, 7 (wght {inst_wght}, slnt {inst_slnt})")

        # drop STAT table to allow RIBBI style naming & linking on Windows
        try:
            del monoFont["STAT"]
        except KeyError:
            print("Font has no STAT table.")

        # In the post table, isFixedPitched flag must be set in the code fonts
        monoFont['post'].isFixedPitch = 1

        # In the OS/2 table Panose bProportion must be set to 9
        monoFont["OS/2"].panose.bProportion = 9

        # Also in the OS/2 table, xAvgCharWidth should be set to 600 rather than 612 (612 is an average of glyphs in the "Mono" files which include wide ligatures).
        monoFont["OS/2"].xAvgCharWidth = 600

        # Apply line height multiplier if specified
        lineHeightMultiplier = fontOptions.get('Line Height Multiplier', 1.0)
        if lineHeightMultiplier != 1.0:
            os2 = monoFont["OS/2"]
            hhea = monoFont["hhea"]

            # Calculate original line height from typo metrics
            # Line height = ascender - descender + lineGap (descender is negative)
            originalLineHeight = os2.sTypoAscender - os2.sTypoDescender + os2.sTypoLineGap
            newLineHeight = int(originalLineHeight * lineHeightMultiplier)

            # Apply the difference to lineGap (keeps glyphs in same position)
            newLineGap = newLineHeight - (os2.sTypoAscender - os2.sTypoDescender)
            os2.sTypoLineGap = max(0, newLineGap)

            # Update hhea table for legacy compatibility
            hhea.lineGap = max(0, newLineGap)

            print(f"\n\t• Line height multiplier: {lineHeightMultiplier}")
            print(f"\t\t Original line height: {originalLineHeight}")
            print(f"\t\t New line height: {newLineHeight}")
            print(f"\t\t New line gap: {os2.sTypoLineGap}")

        # Apply character spacing multiplier if specified
        charSpacing = fontOptions.get('Character Spacing', 1.0)
        if charSpacing != 1.0:
            hmtx = monoFont["hmtx"]
            glyphCount = 0

            for glyphName in hmtx.metrics:
                width, lsb = hmtx.metrics[glyphName]
                newWidth = int(width * charSpacing)
                hmtx.metrics[glyphName] = (newWidth, lsb)
                glyphCount += 1

            # Update xAvgCharWidth to match new spacing
            monoFont["OS/2"].xAvgCharWidth = int(600 * charSpacing)

            print(f"\n\t• Character spacing: {charSpacing}")
            print(f"\t\t Adjusted {glyphCount} glyphs")
            print(f"\t\t New xAvgCharWidth: {monoFont['OS/2'].xAvgCharWidth}")

        # Code to fix fsSelection adapted from:
        # https://github.com/googlefonts/gftools/blob/a0b516d71f9e7988dfa45af2d0822ec3b6972be4/Lib/gftools/fix.py#L764

        old_selection = fs_selection = monoFont["OS/2"].fsSelection

        # turn off all bits except for bit 7 (USE_TYPO_METRICS)
        fs_selection &= 1 << 7

        if instance == "Italic":

            monoFont["head"].macStyle = 0b10
            # In the OS/2 table Panose bProportion must be set to 11 for "oblique boxed" (this is partially a guess)
            monoFont["OS/2"].panose.bLetterForm = 11

            # set Italic bit
            fs_selection |= 1 << 0

        if instance == "Bold":
            monoFont['OS/2'].fsSelection = 0b100000
            monoFont["head"].macStyle = 0b1

            # set Bold bit
            fs_selection |= 1 << 5

        if instance == "Bold Italic":
            monoFont['OS/2'].fsSelection = 0b100001
            monoFont["head"].macStyle = 0b11

            # set Italic & Bold bits
            fs_selection |= 1 << 0
            fs_selection |= 1 << 5


        monoFont["OS/2"].fsSelection = fs_selection


        monoFont.save(outputPath)

        # TTF autohint

        ttfautohint_options.update(
                                    in_file=outputPath,
                                    out_file=outputPath,
                                    hint_composites=True
                                    )

        ttfautohint.ttfautohint()

        print(f"\n→ Font saved to '{outputPath}'\n")


        print('Features are ', fontOptions['Features'])

splitFont()
