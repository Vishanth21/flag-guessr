import json
import time
import urllib.request
import urllib.error
import tempfile
import os
from pathlib import Path
import climage

COUNTRIES = [
    ("Afghanistan",           "af"), ("Albania",              "al"),
    ("Algeria",               "dz"), ("Andorra",              "ad"),
    ("Angola",                "ao"), ("Antigua and Barbuda",  "ag"),
    ("Argentina",             "ar"), ("Armenia",              "am"),
    ("Australia",             "au"), ("Austria",              "at"),
    ("Azerbaijan",            "az"), ("Bahamas",              "bs"),
    ("Bahrain",               "bh"), ("Bangladesh",           "bd"),
    ("Barbados",              "bb"), ("Belarus",              "by"),
    ("Belgium",               "be"), ("Belize",               "bz"),
    ("Benin",                 "bj"), ("Bhutan",               "bt"),
    ("Bolivia",               "bo"), ("Bosnia and Herzegovina","ba"),
    ("Botswana",              "bw"), ("Brazil",               "br"),
    ("Brunei",                "bn"), ("Bulgaria",             "bg"),
    ("Burkina Faso",          "bf"), ("Burundi",              "bi"),
    ("Cabo Verde",            "cv"), ("Cambodia",             "kh"),
    ("Cameroon",              "cm"), ("Canada",               "ca"),
    ("Central African Republic","cf"),("Chad",                 "td"),
    ("Chile",                 "cl"), ("China",                "cn"),
    ("Colombia",              "co"), ("Comoros",              "km"),
    ("Congo",                 "cg"), ("Costa Rica",           "cr"),
    ("Croatia",               "hr"), ("Cuba",                 "cu"),
    ("Cyprus",                "cy"), ("Czech Republic",       "cz"),
    ("DR Congo",              "cd"), ("Denmark",              "dk"),
    ("Djibouti",              "dj"), ("Dominica",             "dm"),
    ("Dominican Republic",    "do"), ("Ecuador",              "ec"),
    ("Egypt",                 "eg"), ("El Salvador",          "sv"),
    ("Equatorial Guinea",     "gq"), ("Eritrea",              "er"),
    ("Estonia",               "ee"), ("Eswatini",             "sz"),
    ("Ethiopia",              "et"), ("Fiji",                 "fj"),
    ("Finland",               "fi"), ("France",               "fr"),
    ("Gabon",                 "ga"), ("Gambia",               "gm"),
    ("Georgia",               "ge"), ("Germany",              "de"),
    ("Ghana",                 "gh"), ("Greece",               "gr"),
    ("Grenada",               "gd"), ("Guatemala",            "gt"),
    ("Guinea",                "gn"), ("Guinea-Bissau",        "gw"),
    ("Guyana",                "gy"), ("Haiti",                "ht"),
    ("Honduras",              "hn"), ("Hungary",              "hu"),
    ("Iceland",               "is"), ("India",                "in"),
    ("Indonesia",             "id"), ("Iran",                 "ir"),
    ("Iraq",                  "iq"), ("Ireland",              "ie"),
    ("Israel",                "il"), ("Italy",                "it"),
    ("Ivory Coast",           "ci"), ("Jamaica",              "jm"),
    ("Japan",                 "jp"), ("Jordan",               "jo"),
    ("Kazakhstan",            "kz"), ("Kenya",                "ke"),
    ("Kiribati",              "ki"), ("Kuwait",               "kw"),
    ("Kyrgyzstan",            "kg"), ("Laos",                 "la"),
    ("Latvia",                "lv"), ("Lebanon",              "lb"),
    ("Lesotho",               "ls"), ("Liberia",              "lr"),
    ("Libya",                 "ly"), ("Liechtenstein",        "li"),
    ("Lithuania",             "lt"), ("Luxembourg",           "lu"),
    ("Madagascar",            "mg"), ("Malawi",               "mw"),
    ("Malaysia",              "my"), ("Maldives",             "mv"),
    ("Mali",                  "ml"), ("Malta",                "mt"),
    ("Marshall Islands",      "mh"), ("Mauritania",           "mr"),
    ("Mauritius",             "mu"), ("Mexico",               "mx"),
    ("Micronesia",            "fm"), ("Moldova",              "md"),
    ("Monaco",                "mc"), ("Mongolia",             "mn"),
    ("Montenegro",            "me"), ("Morocco",              "ma"),
    ("Mozambique",            "mz"), ("Myanmar",              "mm"),
    ("Namibia",               "na"), ("Nauru",                "nr"),
    ("Nepal",                 "np"), ("Netherlands",          "nl"),
    ("New Zealand",           "nz"), ("Nicaragua",            "ni"),
    ("Niger",                 "ne"), ("Nigeria",              "ng"),
    ("North Korea",           "kp"), ("North Macedonia",      "mk"),
    ("Norway",                "no"), ("Oman",                 "om"),
    ("Pakistan",              "pk"), ("Palau",                "pw"),
    ("Palestine",             "ps"), ("Panama",               "pa"),
    ("Papua New Guinea",      "pg"), ("Paraguay",             "py"),
    ("Peru",                  "pe"), ("Philippines",          "ph"),
    ("Poland",                "pl"), ("Portugal",             "pt"),
    ("Qatar",                 "qa"), ("Romania",              "ro"),
    ("Russia",                "ru"), ("Rwanda",               "rw"),
    ("Saint Kitts and Nevis", "kn"), ("Saint Lucia",          "lc"),
    ("Saint Vincent",         "vc"), ("Samoa",                "ws"),
    ("San Marino",            "sm"), ("Sao Tome and Principe","st"),
    ("Saudi Arabia",          "sa"), ("Senegal",              "sn"),
    ("Serbia",                "rs"), ("Seychelles",           "sc"),
    ("Sierra Leone",          "sl"), ("Singapore",            "sg"),
    ("Slovakia",              "sk"), ("Slovenia",             "si"),
    ("Solomon Islands",       "sb"), ("Somalia",              "so"),
    ("South Africa",          "za"), ("South Korea",          "kr"),
    ("South Sudan",           "ss"), ("Spain",                "es"),
    ("Sri Lanka",             "lk"), ("Sudan",                "sd"),
    ("Suriname",              "sr"), ("Sweden",               "se"),
    ("Switzerland",           "ch"), ("Syria",                "sy"),
    ("Taiwan",                "tw"), ("Tajikistan",           "tj"),
    ("Tanzania",              "tz"), ("Thailand",             "th"),
    ("Timor-Leste",           "tl"), ("Togo",                 "tg"),
    ("Tonga",                 "to"), ("Trinidad and Tobago",  "tt"),
    ("Tunisia",               "tn"), ("Turkey",               "tr"),
    ("Turkmenistan",          "tm"), ("Tuvalu",               "tv"),
    ("Uganda",                "ug"), ("Ukraine",              "ua"),
    ("United Arab Emirates",  "ae"), ("United Kingdom",       "gb"),
    ("United States",         "us"), ("Uruguay",              "uy"),
    ("Uzbekistan",            "uz"), ("Vanuatu",              "vu"),
    ("Vatican City",          "va"), ("Venezuela",            "ve"),
    ("Vietnam",               "vn"), ("Yemen",                "ye"),
    ("Zambia",                "zm"), ("Zimbabwe",             "zw"),
]

FLAG_CDN  = "https://flagcdn.com/w160/{code}.png"
OUT_PATH  = Path(__file__).resolve().parent.parent / "data" / "ansi_flags.json"
RENDER_W  = 30

def fetch_flag_png(code: str) -> bytes | None:
    url = FLAG_CDN.format(code=code.lower())
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return resp.read()
    except urllib.error.URLError as e:
        print(f"  ✗  fetch failed ({e})")
        return None


def png_to_ansi(png_bytes: bytes) -> str:
    """Write PNG to a temp file, run climage, return ANSI string."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(png_bytes)
        tmp_path = tmp.name
    try:
        ansi = climage.convert(tmp_path, width=RENDER_W, is_unicode=True, is_truecolor=True, is_256color=False)
        return ansi
    finally:
        os.unlink(tmp_path)


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    results   = []
    skipped   = []
    total     = len(COUNTRIES)

    print(f"Converting {total} flags → {OUT_PATH}\n")

    for i, (country, code) in enumerate(COUNTRIES, start=1):
        print(f"[{i:>3}/{total}] {country} ({code.upper()}) ...", end=" ", flush=True)
        png = fetch_flag_png(code)
        if png is None:
            skipped.append(country)
            continue
        try:
            ansi = png_to_ansi(png)
        except Exception as e:
            print(f"climage error: {type(e).__name__}: {e}")
            skipped.append(country)
            continue
        results.append({"country": country, "code": code.upper(), "ansi": ansi})
        print(f"({len(ansi)} chars)")
        time.sleep(0.05)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nDone. Saved {len(results)} entries to {OUT_PATH}")
    if skipped:
        print(f"Skipped: {', '.join(skipped)}")


if __name__ == "__main__":
    main()