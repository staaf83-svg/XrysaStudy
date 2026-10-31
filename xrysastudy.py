# XrysaStudy — βοηθός διαβάσματος για μαθήματα πανεπιστημίου
import base64
import datetime
import io
import json
import os
import queue
import re
import sys
import tempfile
import threading
import tkinter as tk
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from tkinter import filedialog, messagebox

VERSION = "0.19"
# Το δημόσιο αποθετήριο στο GitHub: από εκεί ελέγχονται και κατεβαίνουν οι νέες εκδόσεις
GITHUB_REPO = "staaf83-svg/XrysaStudy"
# Ο φάκελος του προγράμματος (στο .exe το PyInstaller βάζει τα αρχεία στο sys._MEIPASS)
APP_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
FOLDER_NAMES = {"data": "Τα δεδομένα μου", "study": "Βοηθήματα", "exercise": "Ασκήσεις", "essay": "Εργασίες"}
# Τιμές σε δολάρια ανά εκατομμύριο tokens (Claude Sonnet 5.5). shortcut: γραμμένες με το χέρι, αν αλλάξει
# το μοντέλο ή οι τιμές της Anthropic τις διορθώνουμε εδώ. Gemini = 0 όσο χρησιμοποιείται το δωρεάν όριο.
# Το ChatGPT δεν μετράει ακόμα (είναι γκρι χωρίς κλειδί)· όταν μπει κλειδί, προσθέτουμε την τιμή του.
PRICES = {"Claude": {"in": 2.0, "out": 10.0, "cache_write": 2.5, "cache_read": 0.2},
          "Gemini": {"in": 0.0, "out": 0.0, "cache_write": 0.0, "cache_read": 0.0}}
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
MAX_SOURCES = 15
PROVIDERS = ("Claude", "Gemini", "ChatGPT")
DEFAULT_MODELS = {"Claude": "claude-sonnet-5-5", "Gemini": "gemini-3-flash-preview", "ChatGPT": "gpt-5.6"}
KEY_ENV = {"Claude": "ANTHROPIC_API_KEY", "Gemini": "GEMINI_API_KEY", "ChatGPT": "OPENAI_API_KEY"}
KEY_SITE = {"Claude": "console.anthropic.com", "Gemini": "aistudio.google.com", "ChatGPT": "platform.openai.com"}
CONFIG = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "XrysaStudy", "config.json")
MAX_ROWS = 3000  # shortcut: τεράστια φύλλα/πίνακες κόβονται εδώ, αν χρειαστεί στέλνουμε μόνο τις στήλες που ζητά η άσκηση
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}
FILE_TYPES = [("Υποστηριζόμενα", "*.pdf *.docx *.xlsx *.xlsm *.xls *.pptx *.accdb *.mdb *.csv *.txt "
                                 "*.png *.jpg *.jpeg *.gif *.webp"), ("Όλα", "*.*")]
SECTIONS = {"study": "Βοήθημα", "exercise": "Άσκηση", "essay": "Εργασία"}
SECTION_ICONS = {"study": "📘", "exercise": "🧮", "essay": "📝"}

# Χρώματα και γραμματοσειρές, στο ύφος του PharmDesk
BG = "#f0f0f0"
PANEL = "#ffffff"
BORDER = "#c8c8c8"
TEXT = "#1a1a1a"
MUTED = "#666666"
ACCENT = "#1f6fd1"
FONT = ("Segoe UI", 9)
BOLD = ("Segoe UI", 9, "bold")

FORMAT_RULES = """Κανόνες μορφής: τίτλοι με #, ## ή ###, κουκκίδες που ξεκινούν με "- ", **έντονα**
και `πλάγια εισαγωγικά` για τύπους, εντολές και ονόματα κελιών.
Πίνακες σε μορφή markdown: | Στήλη | Στήλη |, με γραμμή |---|---| κάτω από την επικεφαλίδα.
Σχεδιαγράμματα (μόνο όταν ζητηθούν ή όταν βοηθούν πραγματικά την κατανόηση) ακριβώς σε αυτή τη μορφή:
[ΔΙΑΓΡΑΜΜΑ: τίτλος]
Κουτί Α -> Κουτί Β -> Κουτί Γ : προαιρετική ετικέτα για τα βέλη αυτής της γραμμής
Κουτί Β -> Κουτί Δ
[/ΔΙΑΓΡΑΜΜΑ]
Στα κουτιά σύντομα ονόματα (έως 5 λέξεις)· το πρόγραμμα τα ζωγραφίζει ως εικόνα. Καμία άλλη μορφή εικόνας."""

KEEP_BLOCKS = "Τα σχεδιαγράμματα [ΔΙΑΓΡΑΜΜΑ]…[/ΔΙΑΓΡΑΜΜΑ] και οι πίνακες κρατούν ακριβώς τη μορφή τους."

STUDY_LEVELS = {
    "simple": "ΑΠΛΟ βοήθημα: σύντομο, μόνο τα απαραίτητα, λίγες κουκκίδες ανά θέμα, 5 ερωτήσεις επανάληψης.",
    "detailed": "ΑΝΑΛΥΤΙΚΟ βοήθημα: πλήρεις εξηγήσεις, περισσότερα παραδείγματα, πώς συνδέονται οι έννοιες "
                "μεταξύ τους, 10 έως 15 ερωτήσεις επανάληψης.",
}

STUDY_PROMPT = """Είσαι υπομονετικός καθηγητής που βοηθά μια φοιτήτρια να διαβάσει για το πανεπιστήμιο.
Διάβασε τα συνημμένα αρχεία και φτιάξε ένα βοήθημα διαβάσματος στα ελληνικά, σε απλή γλώσσα.
Είδος: {level}

Δομή:
# <τίτλος του βοηθήματος>
## Με μια ματιά
- τα πιο σημαντικά σημεία
## <μία ενότητα για κάθε κεφάλαιο ή θέμα>
- εξήγηση, με τους βασικούς όρους σε **έντονα** και τον ορισμό τους με απλά λόγια
- παράδειγμα από την καθημερινότητα, όπου βοηθά
## Ερωτήσεις επανάληψης
## Απαντήσεις

Αν η φοιτήτρια ζητήσει κάτι συγκεκριμένο, αυτό έχει προτεραιότητα από τη δομή.
""" + FORMAT_RULES + "\nΜην προσθέτεις πληροφορίες που δεν υπάρχουν στα αρχεία."

EXERCISE_PROMPT = """Είσαι υπομονετικός καθηγητής που βοηθά μια φοιτήτρια να λύσει μια άσκηση πανεπιστημίου
(συνήθως σε Excel, Word ή Access). Λύσε την άσκηση στα ελληνικά, ακολουθώντας τον τρόπο και την ορολογία
των σημειώσεων του μαθήματος, όπου υπάρχουν στα συνημμένα αρχεία.

Δομή:
# Λύση άσκησης
## Τι ζητάει η άσκηση
- με απλά λόγια
## Βήμα 1, Βήμα 2, … (ένας τίτλος ## για κάθε βήμα)
- τι κάνουμε, πού ακριβώς (μενού, καρτέλα, κελί) και **γιατί**
- για Excel: τον ακριβή τύπο, π.χ. `=AVERAGE(B2:B20)`, και σε ποιο κελί μπαίνει
- για Access: τα βήματα για πίνακες, σχέσεις και ερωτήματα, και το SQL όπου βοηθά
- για Word: τα βήματα με τα ονόματα των μενού όπως είναι στο ελληνικό Office
## Αποτέλεσμα
- τι πρέπει να βγει στο τέλος, με τις τιμές όπου μπορούν να υπολογιστούν από τα δεδομένα
## Τι να θυμάσαι
- 2 έως 4 σημεία που θα χρειαστούν και σε παρόμοιες ασκήσεις

Τα δεδομένα Excel δίνονται κελί-κελί, π.χ. `B3=12`. Αν κάτι λείπει από την εκφώνηση, πες το καθαρά.
""" + FORMAT_RULES

ESSAY_PROMPT = """Είσαι έμπειρος ακαδημαϊκός που βοηθά μια φοιτήτρια να γράψει μια εργασία πανεπιστημίου στα ελληνικά.
Γράψε την εργασία σύμφωνα με το θέμα και τις οδηγίες της, χρησιμοποιώντας τα συνημμένα αρχεία ως πηγές.

Δομή:
# <τίτλος εργασίας>
## Εισαγωγή
## <ενότητες του κυρίως θέματος, με δικούς τους τίτλους>
## Συμπεράσματα
## Πηγές
- μόνο τα συνημμένα αρχεία ή πηγές που αναφέρονται μέσα σε αυτά· ποτέ επινοημένες πηγές
- οι πηγές γράφονται όπως στο πρωτότυπο, χωρίς μετάφραση

Γράψε σε κανονικές παραγράφους (όχι κουκκίδες), με σαφή, ακαδημαϊκό αλλά κατανοητό λόγο.
Αν δεν υπάρχουν συνημμένα αρχεία, γράψε από γενικές γνώσεις και σημείωσε στις Πηγές ότι πρέπει να προστεθούν.
""" + FORMAT_RULES

CHAT_PROMPT = """Είσαι υπομονετικός καθηγητής που βοηθά μια φοιτήτρια στο διάβασμα, στις ασκήσεις και στις εργασίες της.
Απάντα στα ελληνικά, σύντομα και με απλά λόγια, με βάση το υλικό που σου δόθηκε (αρχεία και κείμενο στην οθόνη).
Αν η ερώτηση δεν καλύπτεται από το υλικό, πες το και απάντησε γενικά."""

HUMANIZE_PROMPT = """Ξαναγράψε το κείμενο που θα σου δοθεί ώστε να διαβάζεται σαν να το έγραψε μια φοιτήτρια
με τα δικά της λόγια, στα ελληνικά:
- φυσικές, απλές προτάσεις με ποικιλία στο μήκος· παράγραφοι αντί για κουκκίδες όπου ταιριάζει
- καθόλου τυποποιημένες φράσεις όπως «Ας δούμε», «Συνοπτικά», «Συμπερασματικά», «Είναι σημαντικό να σημειωθεί»,
  «Σε αυτό το σημείο», ούτε υπερβολικός ενθουσιασμός
- λίγα έντονα, μόνο όπου πραγματικά χρειάζονται
Μην αλλάξεις το περιεχόμενο: αριθμοί, αποτελέσματα, τύποι Excel, SQL, ονόματα κελιών και μενού μένουν ακριβώς ίδια.
Οι παραπομπές και η Βιβλιογραφία/Πηγές μένουν ακριβώς ίδιες, αμετάφραστες.
Κράτα τους τίτλους. Επέστρεψε μόνο το νέο κείμενο, χωρίς σχόλια.
""" + KEEP_BLOCKS + "\n" + FORMAT_RULES

MERGE_NOTE = """Παραπάνω υπάρχουν και απαντήσεις άλλων μοντέλων στην ίδια εργασία. Σύγκρινέ τες με τη δική σου σκέψη:
κράτα ό,τι σωστό και χρήσιμο προσθέτουν, διόρθωσε ό,τι είναι λάθος και βγάλε μία τελική απάντηση στη δομή
που ζητήθηκε. Μην αναφέρεις τα άλλα μοντέλα μέσα στο κείμενο."""

GREEK_RULE = "Γράφε σε άψογα ελληνικά, με σωστή ορθογραφία, τονισμό, σύνταξη και στίξη."

PROOF_PROMPT = """Είσαι επιμελητής κειμένων. Κάνε ορθογραφικό και συντακτικό έλεγχο στο ελληνικό κείμενο που θα σου δοθεί
και διόρθωσε μόνο τα λάθη:
- ορθογραφία (π.χ. ει/η/ι/οι/υ, ο/ω, διπλά σύμφωνα, καταλήξεις)
- τονισμός και διαλυτικά, τελικό -ν όπου χρειάζεται
- σύνταξη και γραμματική: συμφωνία γένους, αριθμού και πτώσης, «που/πού», «πως/πώς», σωστές πτώσεις
- στίξη: κόμματα, άνω τελεία, ελληνικό ερωτηματικό (;), εισαγωγικά «»
ΜΗΝ αλλάξεις περιεχόμενο, ύφος, σειρά, τίτλους ή μορφοποίηση (#, -, **, `). Αριθμοί, τύποι Excel, SQL,
ονόματα κελιών, αγγλικοί όροι, παραπομπές και ολόκληρη η Βιβλιογραφία/Πηγές μένουν ακριβώς ίδια (χωρίς μετάφραση).
Επέστρεψε μόνο το διορθωμένο κείμενο, χωρίς σχόλια.\n""" + KEEP_BLOCKS

EDIT_PROMPT = """Θα σου δοθεί ένα έτοιμο κείμενο (=== ΚΕΙΜΕΝΟ ===) και οι αλλαγές που ζητά η φοιτήτρια.
ΜΗΝ ξαναγράψεις το κείμενο. Επέστρεψε ΜΟΝΟ τις αλλαγές, η καθεμία σε αυτή ακριβώς τη μορφή:
<<<ΒΡΕΣ
κομμάτι του κειμένου, αντιγραμμένο χαρακτήρα προς χαρακτήρα (αρκετά μεγάλο ώστε να είναι μοναδικό)
===
το νέο κομμάτι που μπαίνει στη θέση του
>>>
- Διαγραφή: άφησε κενό το νέο κομμάτι.
- Προσθήκη: στο ΒΡΕΣ βάλε το υπάρχον κομμάτι μετά το οποίο μπαίνει η προσθήκη, και στο νέο κομμάτι
  γράψε το ίδιο κομμάτι και από κάτω την προσθήκη.
- Άλλαξε μόνο ό,τι ζητήθηκε· το υπόλοιπο κείμενο πρέπει να μείνει ίδιο.
- Νέο σχεδιάγραμμα ή πίνακας: ως προσθήκη, στη μορφή που ορίζουν οι κανόνες παρακάτω.
- Αν υπάρχουν επιστημονικά άρθρα: νέες πληροφορίες μόνο από αυτά, με παραπομπές στη μορφή της εργασίας, και αν προσθέσεις νέα
  παραπομπή, πρόσθεσε με ξεχωριστή αλλαγή και το άρθρο στη Βιβλιογραφία, όπως στο πρωτότυπο, χωρίς μετάφραση.
""" + FORMAT_RULES

EDIT_BLOCK = re.compile(r"<<<ΒΡΕΣ\n(.*?)\n===\n(.*?)\n?>>>", re.S)

QUERY_PROMPT = """Μετέτρεψε το θέμα της εργασίας σε 2 σύντομα ερωτήματα αναζήτησης στα αγγλικά, κατάλληλα για
PubMed και OpenAlex (λέξεις-κλειδιά, όχι προτάσεις). Απάντησε μόνο με τα 2 ερωτήματα, ένα σε κάθε γραμμή."""

CITATION_NOTE = """ΕΠΙΣΗΜΕΣ ΠΗΓΕΣ: Στηρίξου στα επιστημονικά άρθρα της ενότητας «=== ΕΠΙΣΤΗΜΟΝΙΚΑ ΑΡΘΡΑ ===».
- Η εργασία γράφεται ΟΛΗ στα ελληνικά, εκτός από τη Βιβλιογραφία (βλ. παρακάτω). Μετάφρασε με ακρίβεια ό,τι χρησιμοποιείς από τις αγγλικές περιλήψεις.
  Στους επιστημονικούς όρους γράψε τον ελληνικό όρο και, την πρώτη φορά, τον αγγλικό σε παρένθεση.
- Παραπομπές μέσα στο κείμενο και Βιβλιογραφία ακριβώς σύμφωνα με τη ΜΟΡΦΗ ΠΑΡΑΠΟΜΠΩΝ που ορίζεται.
- Αναφέρσου ΜΟΝΟ σε άρθρα της λίστας, ποτέ σε άλλες πηγές, και γράψε μόνο ό,τι στηρίζεται στις περιλήψεις τους.
- Στη θέση της ενότητας «Πηγές» βάλε «## Βιβλιογραφία», μόνο με τα άρθρα που χρησιμοποίησες, με τη σειρά που
  ορίζει η μορφή παραπομπών, και στο τέλος κάθε εγγραφής τον σύνδεσμο DOI (https://doi.org/…) ή, αν δεν υπάρχει, PubMed.
- Η Βιβλιογραφία ΔΕΝ μεταφράζεται: συγγραφείς, τίτλοι άρθρων και ονόματα περιοδικών γράφονται ακριβώς όπως
  στο πρωτότυπο, χωρίς μετάφραση και χωρίς σχόλια σε αγκύλες. Και μέσα στο κείμενο κράτα «et al.» όπου το προβλέπει η μορφή."""

# Μορφές παραπομπών: όνομα → περιγραφή για το Claude
CITATION_STYLES = {
    "APA 7": "APA 7η έκδοση. Μέσα στο κείμενο: (Επώνυμο, έτος), (Επώνυμο & Επώνυμο, έτος), (Επώνυμο et al., έτος). "
             "Βιβλιογραφία αλφαβητικά: Επώνυμο, Α. Β., & Επώνυμο, Γ. (έτος). Τίτλος. *Περιοδικό*, τόμος(τεύχος), σελίδες. https://doi.org/…",
    "Harvard": "Harvard. Μέσα στο κείμενο: (Επώνυμο έτος) ή (Επώνυμο et al. έτος). Βιβλιογραφία αλφαβητικά: "
               "Επώνυμο, Α. και Επώνυμο, Β. (έτος) 'Τίτλος', *Περιοδικό*, τόμος(τεύχος), σσ. …. Διαθέσιμο σε: https://doi.org/…",
    "Vancouver": "Vancouver. Μέσα στο κείμενο αριθμοί σε αγκύλες [1], [2] με τη σειρά πρώτης εμφάνισης. Βιβλιογραφία "
                 "αριθμημένη με τη σειρά εμφάνισης (όχι αλφαβητικά): 1. Επώνυμο ΑΒ, Επώνυμο ΓΔ. Τίτλος. Περιοδικό. έτος;τόμος(τεύχος):σελίδες. doi:…",
    "MLA 9": "MLA 9. Μέσα στο κείμενο: (Επώνυμο) ή (Επώνυμο et al.). Βιβλιογραφία (Works Cited) αλφαβητικά: "
             "Επώνυμο, Όνομα, et al. \"Τίτλος.\" *Περιοδικό*, τόμ. Χ, αρ. Υ, έτος, σσ. …, https://doi.org/…",
    "Chicago (συγγραφέας-έτος)": "Chicago author-date. Μέσα στο κείμενο: (Επώνυμο έτος). Βιβλιογραφία αλφαβητικά: "
                                 "Επώνυμο, Όνομα. έτος. \"Τίτλος.\" *Περιοδικό* τόμος (τεύχος): σελίδες. https://doi.org/…",
    "IEEE": "IEEE. Μέσα στο κείμενο αριθμοί σε αγκύλες [1] με τη σειρά πρώτης εμφάνισης. Βιβλιογραφία αριθμημένη: "
            "[1] Α. Επώνυμο και Β. Επώνυμο, \"Τίτλος,\" *Περιοδικό*, τόμ. Χ, αρ. Υ, σσ. …, έτος, doi: ….",
}
CUSTOM_STYLE = "Δικό μου παράδειγμα…"


def citation_rule(cfg):
    """Η οδηγία για τη μορφή παραπομπών που διάλεξε η χρήστρια (έτοιμη μορφή ή δικό της παράδειγμα)."""
    example = cfg.get("citation_example", "").strip()
    if cfg.get("citation_style") == CUSTOM_STYLE and example:
        return ("ΜΟΡΦΗ ΠΑΡΑΠΟΜΠΩΝ: ακολούθησε ΑΚΡΙΒΩΣ τη μορφή αυτού του παραδείγματος (σειρά, στίξη, πλάγια, "
                "αριθμοί), και μέσα στο κείμενο και στη Βιβλιογραφία:\n" + example)
    return "ΜΟΡΦΗ ΠΑΡΑΠΟΜΠΩΝ: " + CITATION_STYLES.get(cfg.get("citation_style"), CITATION_STYLES["APA 7"])

STRICT_NOTE = """ΑΥΣΤΗΡΟΣ ΚΑΝΟΝΑΣ: Απάντα μόνο με βάση τα συνημμένα αρχεία.
Ακολούθησε τη μέθοδο, τα βήματα και την ορολογία τους, ακόμα κι αν ξέρεις άλλον τρόπο.
Αν κάτι δεν καλύπτεται από τα αρχεία, γράψε καθαρά «Αυτό δεν υπάρχει στα αρχεία» αντί να απαντήσεις από γενικές γνώσεις."""


def load_config():
    try:
        with open(CONFIG, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        cfg = {}
    cfg.setdefault("keys", {})
    if "api_key" in cfg:  # μορφή της v0.1/v0.2: ένα μόνο κλειδί, του Claude
        cfg["keys"].setdefault("Claude", cfg.pop("api_key"))
    cfg["models"] = {**DEFAULT_MODELS, **cfg.get("models", {})}
    if cfg["models"]["Gemini"] == "gemini-3.1-pro-preview":  # παλιά προεπιλογή, χωρίς δωρεάν όριο
        cfg["models"]["Gemini"] = DEFAULT_MODELS["Gemini"]
    cfg.setdefault("instructions", "")    # μόνιμες οδηγίες της χρήστριας
    cfg.setdefault("official", False)     # «Από επίσημες πηγές» στην Εργασία
    cfg.setdefault("autoproof", False)    # αυτόματος ορθογραφικός έλεγχος μετά από κάθε αποτέλεσμα
    cfg.setdefault("citation_style", "APA 7")
    cfg.setdefault("citation_example", "")  # το δικό της παράδειγμα παραπομπής
    cfg.setdefault("costs", {})           # μετρητής κόστους: τελευταίο, σήμερα, μήνας
    # Κάθε section θυμάται τα δικά του αρχεία· οι σημειώσεις της v0.6 πάνε στην «Άσκηση»
    cfg["files"] = {"study": [], "exercise": cfg.pop("notes", []), "essay": [], **cfg.get("files", {})}
    cfg["only"] = {"study": False, "exercise": cfg.pop("notes_only", False), "essay": False, **cfg.get("only", {})}
    return cfg


def documents_dir():
    """Ο πραγματικός φάκελος «Έγγραφα» (σωστός και όταν τα Έγγραφα είναι μεταφερμένα στο OneDrive)."""
    import ctypes
    buf = ctypes.create_unicode_buffer(260)
    if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and os.path.isdir(buf.value):  # 5 = Έγγραφα
        return buf.value
    return os.path.join(os.path.expanduser("~"), "Documents")


def ensure_folders(base):
    """Φτιάχνει (αν λείπουν) τον φάκελο XrysaStudy και τους υποφακέλους του· επιστρέφει τις διαδρομές τους."""
    folders = {key: os.path.join(base, name) for key, name in FOLDER_NAMES.items()}
    folders["base"] = base
    for path in folders.values():
        try:
            os.makedirs(path, exist_ok=True)
        except OSError:
            pass  # χωρίς φάκελο τα παράθυρα επιλογής απλώς ανοίγουν στη συνηθισμένη θέση των Windows
    return folders


def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


class SourceError(Exception):
    """Πρόβλημα στην αναζήτηση επιστημονικών πηγών· το μήνυμα δείχνεται όπως είναι."""


def friendly_error(provider, e):
    """Μετατρέπει τα συνηθισμένα σφάλματα σε μήνυμα που καταλαβαίνει κανείς."""
    if isinstance(e, SourceError):
        return str(e)
    text = str(e)
    if "429" in text or "RESOURCE_EXHAUSTED" in text or "rate_limit" in text:
        if provider == "Gemini":
            return ("Τελείωσε το δωρεάν όριο του Gemini για την ώρα. Ξαναδοκίμασε σε λίγα λεπτά ή αύριο, "
                    "ή ενεργοποίησε χρέωση στο aistudio.google.com.")
        return (f"Το {provider} λέει ότι ξεπεράστηκε το όριο χρήσης ή δεν υπάρχει υπόλοιπο. "
                f"Ξαναδοκίμασε σε λίγο ή έλεγξε τον λογαριασμό στο {KEY_SITE[provider]}.")
    if "API key not valid" in text or "401" in text or "authentication" in text.lower():
        return f"Το κλειδί του {provider} δεν είναι σωστό. Έλεγξέ το στις «Ρυθμίσεις»."
    return f"{provider}: {text}"


# ---------- ανάγνωση αρχείων ----------
def read_excel(path):
    """Γράφει κάθε μη κενό κελί ως Β3=τιμή, ώστε το μοντέλο να ξέρει ακριβώς πού βρίσκεται."""
    from openpyxl import load_workbook
    wb = load_workbook(path, read_only=True)
    out = []
    for ws in wb.worksheets:
        out.append(f"Φύλλο «{ws.title}»:")
        for n, row in enumerate(ws.iter_rows(), 1):
            if n > MAX_ROWS:
                out.append("… (οι υπόλοιπες γραμμές κόπηκαν)")
                break
            cells = [f"{c.coordinate}={c.value}" for c in row if getattr(c, "value", None) is not None]
            if cells:
                out.append("  ".join(cells))
    wb.close()
    return "\n".join(out)


def read_xls(path):
    """Παλιό Excel (.xls), στην ίδια μορφή κελί-κελί."""
    import xlrd
    from openpyxl.utils import get_column_letter
    out = []
    for sh in xlrd.open_workbook(path).sheets():
        out.append(f"Φύλλο «{sh.name}»:")
        for r in range(min(sh.nrows, MAX_ROWS)):
            cells = [f"{get_column_letter(c + 1)}{r + 1}={v}" for c, v in enumerate(sh.row_values(r)) if v != ""]
            if cells:
                out.append("  ".join(cells))
    return "\n".join(out)


def read_docx(path):
    import docx
    d = docx.Document(path)
    lines = [p.text for p in d.paragraphs if p.text.strip()]
    for t in d.tables:
        lines += [" | ".join(c.text.strip() for c in r.cells) for r in t.rows]
    return "\n".join(lines)


def read_pptx(path):
    from pptx import Presentation
    out = []
    for i, slide in enumerate(Presentation(path).slides, 1):
        out.append(f"Διαφάνεια {i}:")
        for sh in slide.shapes:
            if sh.has_text_frame and sh.text_frame.text.strip():
                out.append(sh.text_frame.text)
            if getattr(sh, "has_table", False):
                out += [" | ".join(c.text for c in r.cells) for r in sh.table.rows]
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame.text.strip():
            out.append("Σημειώσεις ομιλητή: " + slide.notes_slide.notes_text_frame.text)
    return "\n".join(out)


def read_access(path):
    """Πίνακες Access: στήλες με τον τύπο τους και τις εγγραφές. Χρειάζεται τον οδηγό Access των Windows."""
    import pyodbc
    conn = pyodbc.connect(r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + path + ";", readonly=True)
    try:
        cur = conn.cursor()
        tables = [t.table_name for t in cur.tables(tableType="TABLE")]
        queries = [t.table_name for t in cur.tables(tableType="VIEW")]
        out = []
        for t in tables:
            cols = [f"{c.column_name} ({c.type_name})" for c in cur.columns(table=t)]
            out.append(f"Πίνακας «{t}» — στήλες: " + ", ".join(cols))
            cur.execute(f"SELECT * FROM [{t}]")
            out += ["  " + " | ".join("" if v is None else str(v) for v in row) for row in cur.fetchmany(MAX_ROWS)]
        if queries:
            out.append("Αποθηκευμένα ερωτήματα: " + ", ".join(queries))
        return "\n".join(out)
    finally:
        conn.close()


def read_text(path):
    for enc in ("utf-8-sig", "cp1253"):
        try:
            with open(path, encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            pass
    raise ValueError(f"Δεν μπορώ να διαβάσω το {os.path.basename(path)}")


READERS = {".xlsx": read_excel, ".xlsm": read_excel, ".xls": read_xls, ".docx": read_docx,
           ".pptx": read_pptx, ".accdb": read_access, ".mdb": read_access}


def file_block(path):
    """Μετατρέπει ένα αρχείο σε κομμάτι μηνύματος (στη μορφή του Claude· τα άλλα μοντέλα το μετατρέπουν)."""
    name = os.path.basename(path)
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf" or ext in IMAGE_TYPES:
        with open(path, "rb") as f:
            data = base64.standard_b64encode(f.read()).decode()
        if ext == ".pdf":
            return {"type": "document", "title": name,
                    "source": {"type": "base64", "media_type": "application/pdf", "data": data}}
        return {"type": "image", "source": {"type": "base64", "media_type": IMAGE_TYPES[ext], "data": data}}
    text = READERS.get(ext, read_text)(path)
    return {"type": "text", "text": f"--- Αρχείο: {name} ---\n{text}"}


# ---------- έκδοση και αναβαθμίσεις ----------
def version_tuple(v):
    """«v0.14» → (0, 14), ώστε να συγκρίνονται σωστά (0.14 > 0.9)."""
    return tuple(int(n) for n in re.findall(r"\d+", v))


def latest_release(repo):
    """Η τελευταία δημοσιευμένη έκδοση στο GitHub: (έκδοση, σελίδα λήψης, σύνδεσμος του Setup.exe ή None)."""
    data = json.loads(http_get(f"https://api.github.com/repos/{repo}/releases/latest"))
    setup = next((a["browser_download_url"] for a in data.get("assets", []) if a["name"].lower().endswith("setup.exe")), None)
    return data["tag_name"].lstrip("v"), data["html_url"], setup


def read_changelog():
    try:
        with open(os.path.join(APP_DIR, "CHANGELOG.md"), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return "# Ιστορικό αλλαγών\nΔεν βρέθηκε το αρχείο CHANGELOG.md."


# ---------- κόστος ----------
def cost_of(provider, usage):
    """Κόστος σε δολάρια από τα tokens μιας κλήσης."""
    prices = PRICES.get(provider, {})
    return sum(usage.get(kind, 0) * price for kind, price in prices.items()) / 1_000_000


def add_cost(costs, amount, today, tokens=0):
    """Προσθέτει κόστος και tokens στο «Σήμερα» και στον «Μήνα»· μηδενίζει όταν αλλάξει η μέρα ή ο μήνας."""
    day, month = today.isoformat(), today.isoformat()[:7]
    if costs.get("day") != day:
        costs.update(day=day, today=0.0, today_tokens=0)
    if costs.get("month") != month:
        costs.update(month=month, month_total=0.0, month_tokens=0)
    costs.update(last=amount, last_tokens=tokens)
    costs["today"] += amount
    costs["month_total"] += amount
    costs["today_tokens"] = costs.get("today_tokens", 0) + tokens  # get: ρυθμίσεις της v0.11 δεν είχαν tokens
    costs["month_tokens"] = costs.get("month_tokens", 0) + tokens
    return costs


def money(x):
    """0.0684 → «0,068$» (ελληνική υποδιαστολή)."""
    return f"{x:.3f}$".replace(".", ",") if x < 1 else f"{x:.2f}$".replace(".", ",")


def count_fmt(n):
    """12345 → «12.345» (ελληνική μορφή χιλιάδων)."""
    return f"{n:,}".replace(",", ".")


# ---------- έλεγχος πρωτοτυπίας ----------
COPY_WORDS = 8  # τόσες συνεχόμενες ίδιες λέξεις με μια πηγή θεωρούνται αυτούσια αντιγραφή

ORIG_PROMPT = """Είσαι ελεγκτής πρωτοτυπίας ακαδημαϊκών εργασιών. Σύγκρινε την εργασία («=== ΕΡΓΑΣΙΑ ===») με τις πηγές.
Βρες κομμάτια της εργασίας που είναι σχεδόν αυτούσια ίδια με κάποια πηγή, ή πιστή μετάφραση / πολύ κοντινή
παράφραση πηγής, χωρίς εισαγωγικά. ΜΗΝ αναφέρεις κομμάτια που απλώς χρησιμοποιούν την ίδια πληροφορία
με δικά τους λόγια. Για κάθε κομμάτι γράψε ακριβώς:
<<<ΚΟΜΜΑΤΙ
το κομμάτι της εργασίας, αντιγραμμένο χαρακτήρα προς χαρακτήρα (μία πρόταση ή λιγότερο)
===
Πηγή: <ποια πηγή> · Γιατί: <μία σύντομη πρόταση στα ελληνικά>
>>>
Αν δεν βρεις τίποτα, γράψε μόνο: ΚΑΘΑΡΟ"""

ORIG_BLOCK = re.compile(r"<<<ΚΟΜΜΑΤΙ\n(.*?)\n===\n(.*?)\n?>>>", re.S)


def source_text(path):
    """Το κείμενο ενός αρχείου για τη σύγκριση (οι εικόνες δεν έχουν κείμενο)."""
    ext = os.path.splitext(path)[1].lower()
    if ext in IMAGE_TYPES:
        return ""
    if ext == ".pdf":
        from pypdf import PdfReader
        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    return READERS.get(ext, read_text)(path)


def _words(text):
    """Οι λέξεις του κειμένου χωρίς τόνους και κεφαλαία, με τη θέση τους: [(λέξη, αρχή, τέλος)]."""
    out = []
    for m in re.finditer(r"\w+", text):
        w = "".join(c for c in unicodedata.normalize("NFD", m.group().lower()) if not unicodedata.combining(c))
        out.append((w, m.start(), m.end()))
    return out


def find_copied(text, sources, n=COPY_WORDS):
    """Κομμάτια του text με ≥ n συνεχόμενες λέξεις ίδιες με κάποια πηγή.
    Επιστρέφει ([(αρχή, τέλος, πηγή)], ποσοστό % των λέξεων που είναι αντιγραμμένες)."""
    grams = {}
    for name, src in sources.items():
        ws = [w for w, _, _ in _words(src)]
        for i in range(len(ws) - n + 1):
            grams.setdefault(tuple(ws[i:i + n]), name)
    words = _words(text)
    covered = [None] * len(words)
    for i in range(len(words) - n + 1):
        name = grams.get(tuple(w for w, _, _ in words[i:i + n]))
        if name:
            covered[i:i + n] = [name] * n
    spans, i = [], 0
    while i < len(words):
        if covered[i]:
            j = i
            while j + 1 < len(words) and covered[j + 1]:
                j += 1
            spans.append((words[i][1], words[j][2], covered[i]))
            i = j + 1
        else:
            i += 1
    pct = round(100 * sum(1 for c in covered if c) / len(words)) if words else 0
    return spans, pct


def strip_references(text):
    """Κόβει τη Βιβλιογραφία/Πηγές στο τέλος: εκεί η ομοιότητα με τις πηγές είναι φυσική."""
    m = re.search(r"^\s*(Βιβλιογραφία|Πηγές|References)\s*$", text, re.M)
    return text[:m.start()] if m else text


# ---------- αλλαγές σε έτοιμο κείμενο ----------
def parse_edits(reply):
    """Βγάζει τις αλλαγές (ΒΡΕΣ → νέο κομμάτι) από την απάντηση του Claude."""
    return EDIT_BLOCK.findall(reply)


def apply_edits(text, edits):
    """Εφαρμόζει τις αλλαγές μία-μία· ό,τι δεν βρίσκεται στο κείμενο παραλείπεται, ώστε το κείμενο να μη χαλάει ποτέ."""
    applied, failed = [], 0
    for find, new in edits:
        if find and find in text:
            text = text.replace(find, new, 1)
            applied.append(new)
        else:
            failed += 1
    return text, applied, failed


# ---------- επιστημονικές πηγές (PubMed, OpenAlex: δωρεάν, χωρίς κλειδί) ----------
def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": f"XrysaStudy/{VERSION}"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def parse_pubmed(xml_bytes):
    """Από το XML του PubMed κρατά τίτλο, συγγραφείς, έτος, περιοδικό, DOI, PMID και περίληψη."""
    out = []
    for art in ET.fromstring(xml_bytes).iter("PubmedArticle"):
        def text(path):
            el = art.find(path)
            return "".join(el.itertext()).strip() if el is not None else ""
        ids = art.find("PubmedData/ArticleIdList")
        doi = next((i.text for i in (ids if ids is not None else []) if i.get("IdType") == "doi"), "") or ""
        year = text(".//JournalIssue/PubDate/Year") or text(".//JournalIssue/PubDate/MedlineDate")[:4]
        out.append({
            "title": text(".//Article/ArticleTitle"),
            "authors": [f"{a.findtext('LastName')} {a.findtext('Initials') or ''}".strip()
                        for a in art.findall(".//Article/AuthorList/Author") if a.findtext("LastName")],
            "year": year, "journal": text(".//Article/Journal/Title"), "doi": doi,
            "pmid": text("MedlineCitation/PMID"),
            "abstract": " ".join("".join(t.itertext()) for t in art.findall(".//Article/Abstract/AbstractText")),
        })
    return out


def search_pubmed(query, n=5):
    q = urllib.parse.quote(query)
    found = json.loads(http_get(f"{EUTILS}/esearch.fcgi?db=pubmed&retmode=json&sort=relevance&retmax={n}&term={q}"))
    ids = found["esearchresult"]["idlist"]
    return parse_pubmed(http_get(f"{EUTILS}/efetch.fcgi?db=pubmed&retmode=xml&id={','.join(ids)}")) if ids else []


def openalex_abstract(inverted):
    """Το OpenAlex δίνει την περίληψη ως «λέξη → θέσεις»· την ξαναφτιάχνουμε σε κείμενο."""
    return " ".join(w for _, w in sorted((pos, w) for w, positions in (inverted or {}).items() for pos in positions))


def search_openalex(query, n=4):
    q = urllib.parse.quote(query)
    data = json.loads(http_get(f"https://api.openalex.org/works?per-page={n}&filter=has_abstract:true&search={q}"))
    out = []
    for w in data.get("results", []):
        source = (w.get("primary_location") or {}).get("source") or {}
        out.append({
            "title": w.get("display_name") or "",
            "authors": [a["author"]["display_name"] for a in w.get("authorships", []) if a.get("author")],
            "year": str(w.get("publication_year") or ""), "journal": source.get("display_name") or "",
            "doi": (w.get("doi") or "").replace("https://doi.org/", ""), "pmid": "",
            "abstract": openalex_abstract(w.get("abstract_inverted_index")),
        })
    return out


def find_sources(queries):
    """Ψάχνει σε PubMed και OpenAlex και κρατά έως MAX_SOURCES άρθρα χωρίς διπλά."""
    sources, seen = [], set()
    for q in queries:
        for s in search_pubmed(q) + search_openalex(q):
            ident = (s["doi"] or s["title"]).lower()
            if s["title"] and s["abstract"] and ident not in seen:
                seen.add(ident)
                sources.append(s)
    return sources[:MAX_SOURCES]


def format_sources(sources):
    lines = []
    for i, s in enumerate(sources, 1):
        authors = ", ".join(s["authors"][:6]) + (" et al." if len(s["authors"]) > 6 else "")
        links = [f"DOI: https://doi.org/{s['doi']}" if s["doi"] else "",
                 f"PubMed: https://pubmed.ncbi.nlm.nih.gov/{s['pmid']}/" if s["pmid"] else ""]
        lines.append(f"[{i}] {authors} ({s['year']}). {s['title']} {s['journal']}. {' | '.join(l for l in links if l)}\n"
                     f"Περίληψη: {s['abstract'][:1500]}")  # shortcut: μακριές περιλήψεις κόβονται για μικρότερο κόστος
    return "\n\n".join(lines)


# ---------- σύνδεση με τα τρία μοντέλα ----------
def to_gemini_parts(content):
    from google.genai import types
    return [types.Part.from_text(text=b["text"]) if b["type"] == "text" else
            types.Part.from_bytes(data=base64.b64decode(b["source"]["data"]), mime_type=b["source"]["media_type"])
            for b in content]


def to_openai_items(content):
    items = []
    for b in content:
        if b["type"] == "text":
            items.append({"type": "input_text", "text": b["text"]})
            continue
        url = f"data:{b['source']['media_type']};base64,{b['source']['data']}"
        if b["type"] == "image":
            items.append({"type": "input_image", "image_url": url})
        else:
            items.append({"type": "input_file", "filename": b.get("title", "file.pdf"), "file_data": url})
    return items


def stream_reply(provider, key, model, system, messages, usage=None):
    """Επιστρέφει την απάντηση κομμάτι-κομμάτι, όπως γράφεται. Στο usage προσθέτει τα tokens που χρεώθηκαν."""
    usage = {} if usage is None else usage

    def count(**tokens):
        for name, n in tokens.items():
            usage[name] = usage.get(name, 0) + (n or 0)

    if provider == "Claude":
        import anthropic
        with anthropic.Anthropic(api_key=key).messages.stream(
                model=model, max_tokens=16000, system=system, messages=messages) as stream:
            yield from stream.text_stream
            u = stream.get_final_message().usage
            count(**{"in": u.input_tokens, "out": u.output_tokens,
                     "cache_write": u.cache_creation_input_tokens, "cache_read": u.cache_read_input_tokens})
    elif provider == "Gemini":
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=key)  # σε μεταβλητή: αλλιώς η σύνδεση κλείνει πριν σταλεί το αίτημα
        last = None
        # Gemini και ChatGPT παίρνουν μόνο εργασίες μίας ερώτησης, όχι συζήτηση
        for chunk in client.models.generate_content_stream(
                model=model, contents=to_gemini_parts(messages[0]["content"]),
                config=types.GenerateContentConfig(system_instruction=system)):
            last = chunk.usage_metadata or last
            if chunk.text:
                yield chunk.text
        if last:
            count(**{"in": last.prompt_token_count,
                     "out": (last.candidates_token_count or 0) + (last.thoughts_token_count or 0)})
    else:
        from openai import OpenAI
        for event in OpenAI(api_key=key).responses.create(
                model=model, instructions=system, stream=True,
                input=[{"role": "user", "content": to_openai_items(messages[0]["content"])}]):
            if event.type == "response.output_text.delta":
                yield event.delta


# ---------- μορφοποίηση ----------
def line_kind(line):
    """Επιστρέφει (είδος γραμμής, κείμενο χωρίς το σημάδι)."""
    for mark in ("###", "##", "#"):
        if line.startswith(mark + " "):
            return mark, line[len(mark) + 1:]
    if line.startswith(("- ", "* ")):
        return "-", line[2:]
    return "p", line


INLINE = re.compile(r"(\*\*.+?\*\*|`.+?`)")


def inline_parts(text):
    """Χωρίζει το κείμενο σε (κομμάτι, στυλ): στυλ = '', 'b' (έντονα) ή 'code' (τύπος)."""
    for part in INLINE.split(text):
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            yield part[2:-2], "b"
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            yield part[1:-1], "code"
        elif part:
            yield part, ""


def inline_html(text):
    out = []
    for part, kind in inline_parts(text):
        part = part.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        out.append({"b": f"<b>{part}</b>", "code": f'<font name="Consolas">{part}</font>'}.get(kind, part))
    return "".join(out)


# ---------- σχεδιαγράμματα και πίνακες ----------
DIAGRAM_START = re.compile(r"^\[ΔΙΑΓΡΑΜΜΑ:?\s*(.*?)\]$")
DIAGRAM_COLORS = [("#dbeafe", "#3b82f6"), ("#dcfce7", "#22a05a"), ("#fef3c7", "#d99a06"),
                  ("#fce7f3", "#db2777"), ("#ede9fe", "#7c3aed"), ("#cffafe", "#0891b2")]


def parse_diagram(lines):
    """«Α -> Β -> Γ : ετικέτα» → (κουτιά με τη σειρά, βέλη [(από, προς, ετικέτα)])."""
    nodes, edges = [], []
    for line in lines:
        label = ""
        if " : " in line:
            line, label = line.split(" : ", 1)
        parts = [p.strip() for p in re.split(r"->|→", line) if p.strip()]
        nodes += [p for p in parts if p not in nodes]
        edges += [(a, b, label.strip()) for a, b in zip(parts, parts[1:])]
    return nodes, edges


def parse_blocks(md):
    """Χωρίζει το κείμενο σε κομμάτια: ("line", γραμμή), ("diagram", (τίτλος, κουτιά, βέλη)), ("table", γραμμές)."""
    blocks, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        s = lines[i].strip()
        m = DIAGRAM_START.match(s)
        if m:
            body, i = [], i + 1
            while i < len(lines) and lines[i].strip() != "[/ΔΙΑΓΡΑΜΜΑ]":
                if lines[i].strip():
                    body.append(lines[i].strip())
                i += 1
            blocks.append(("diagram", (m.group(1).strip(), *parse_diagram(body))))
            i += 1
        elif s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):  # η γραμμή |---|---| δεν είναι δεδομένα
                    rows.append(cells)
                i += 1
            if rows:
                blocks.append(("table", rows))
        else:
            blocks.append(("line", lines[i]))
            i += 1
    return blocks


def draw_diagram(title, nodes, edges):
    """Ζωγραφίζει το σχεδιάγραμμα: χρωματιστά κουτιά σε στήλες από αριστερά προς τα δεξιά, με βέλη. Επιστρέφει εικόνα PIL."""
    import textwrap
    from PIL import Image, ImageDraw, ImageFont
    S = 2  # σε διπλό μέγεθος, για καθαρή εικόνα και στο PDF
    fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    font = ImageFont.truetype(os.path.join(fonts, "segoeui.ttf"), 15 * S)
    bold = ImageFont.truetype(os.path.join(fonts, "segoeuib.ttf"), 17 * S)
    small = ImageFont.truetype(os.path.join(fonts, "segoeui.ttf"), 12 * S)

    # Στήλη κάθε κουτιού = ο μεγαλύτερος δρόμος από την αρχή· τα βέλη «προς τα πίσω» (κύκλοι) δεν μετράνε
    back, state = set(), {}

    def visit(n):
        state[n] = 1
        for a, b, _ in edges:
            if a == n:
                if state.get(b) == 1:
                    back.add((a, b))
                elif not state.get(b):
                    visit(b)
        state[n] = 2
    for n in nodes:
        if not state.get(n):
            visit(n)
    level = dict.fromkeys(nodes, 0)
    for _ in nodes:
        for a, b, _ in edges:
            if (a, b) not in back:
                level[b] = max(level[b], level[a] + 1)
    # Κουτιά που μόνο «δίνουν» (π.χ. «tRNA → Ριβόσωμα») μπαίνουν ακριβώς πριν από τον στόχο τους,
    # ώστε το βέλος να μη διασχίζει άλλα κουτιά
    incoming = {b for a, b, _ in edges if (a, b) not in back}
    for n in nodes:
        targets = [level[b] for a, b, _ in edges if a == n and (a, b) not in back]
        if n not in incoming and targets:
            level[n] = min(targets) - 1

    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))  # μόνο για να μετράμε πλάτος κειμένου
    line_h, pad, gap_y, margin = 20 * S, 12 * S, 26 * S, 24 * S
    # Απόσταση στηλών: αρκετή ώστε να χωρά η μεγαλύτερη ετικέτα βέλους χωρίς να κρύβει το βέλος
    gap_x = max([70 * S] + [int(measure.textlength(l, font=small)) + 50 * S for _, _, l in edges if l])
    text, size = {}, {}
    for n in nodes:
        text[n] = textwrap.wrap(n, 20) or [n]
        w = max(measure.textlength(t, font=font) for t in text[n])
        size[n] = (int(w) + 2 * pad, len(text[n]) * line_h + 2 * pad)
    columns = [[n for n in nodes if level[n] == c] for c in range(max(level.values(), default=0) + 1)]
    col_w = [max((size[n][0] for n in col), default=0) for col in columns]
    col_h = [sum(size[n][1] for n in col) + gap_y * (len(col) - 1) for col in columns]
    title_h = 40 * S if title else 0
    loop_room = 40 * S if back or any(level[b] <= level[a] for a, b, _ in edges) else 0
    width = max(sum(col_w) + gap_x * (len(columns) - 1) + 2 * margin,
                int(measure.textlength(title, font=bold)) + 2 * margin)
    height = title_h + max(col_h, default=0) + 2 * margin + loop_room

    img = Image.new("RGB", (width, height), "white")
    d = ImageDraw.Draw(img)
    if title:
        d.text((width / 2, margin + title_h / 3), title, font=bold, fill="#1a1a1a", anchor="mm")
    box, x = {}, margin
    for c, col in enumerate(columns):
        y = title_h + margin + (max(col_h) - col_h[c]) / 2
        for n in col:
            w, h = size[n]
            left = x + (col_w[c] - w) / 2
            box[n] = (left, y, left + w, y + h)
            fill, edge = DIAGRAM_COLORS[c % len(DIAGRAM_COLORS)]
            d.rounded_rectangle(box[n], radius=10 * S, fill=fill, outline=edge, width=2 * S)
            for k, t in enumerate(text[n]):
                d.text((left + w / 2, y + pad + k * line_h + line_h / 2), t, font=font, fill="#1a1a1a", anchor="mm")
            y += h + gap_y
        x += col_w[c] + gap_x

    def arrow(points, label):
        d.line(points, fill="#5b6b7f", width=2 * S, joint="curve")
        (x1, y1), (x2, y2) = points[-2], points[-1]
        length = max(((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5, 1)
        ux, uy = (x2 - x1) / length, (y2 - y1) / length
        a = 10 * S
        d.polygon([(x2, y2), (x2 - a * ux - a * 0.6 * uy, y2 - a * uy + a * 0.6 * ux),
                   (x2 - a * ux + a * 0.6 * uy, y2 - a * uy - a * 0.6 * ux)], fill="#5b6b7f")
        if label:
            mx, my = (points[0][0] + points[-1][0]) / 2, (points[0][1] + points[-1][1]) / 2
            if len(points) > 2:
                mx, my = (points[1][0] + points[2][0]) / 2, points[1][1]
            lw = measure.textlength(label, font=small)
            d.rounded_rectangle((mx - lw / 2 - 4 * S, my - 9 * S, mx + lw / 2 + 4 * S, my + 9 * S), radius=4 * S, fill="white")
            d.text((mx, my), label, font=small, fill="#5b6b7f", anchor="mm")

    bottom = height - margin - loop_room / 2
    for a, b, label in edges:
        (al, at, ar, ab), (bl, bt, br, bb) = box[a], box[b]
        if level[b] > level[a]:  # κανονικό βέλος προς τα δεξιά
            arrow([(ar, (at + ab) / 2), (bl, (bt + bb) / 2)], label)
        else:  # βέλος προς τα πίσω ή στην ίδια στήλη: περνά από κάτω
            arrow([((al + ar) / 2, ab), ((al + ar) / 2, bottom), ((bl + br) / 2, bottom), ((bl + br) / 2, bb)], label)
    return img


def diagram_text(title, nodes, edges):
    """Το σχεδιάγραμμα ως απλό κείμενο (για Excel και .txt)."""
    lines = [f"[Σχεδιάγραμμα: {title}]"] + [f"{a} → {b}" + (f" ({l})" if l else "") for a, b, l in edges]
    return lines + [n for n in nodes if not any(n in (a, b) for a, b, _ in edges)]


def plain_line(text):
    """Κείμενο χωρίς τα σημάδια ** και `."""
    return "".join(part for part, _ in inline_parts(text))


def export_docx(md, path):
    """Word με κανονικούς τίτλους, κουκκίδες και έντονα."""
    import docx
    from docx.shared import Cm
    d = docx.Document()
    for block, data in parse_blocks(md):
        if block == "diagram":
            buf = io.BytesIO()
            draw_diagram(*data).save(buf, "PNG")
            d.add_picture(buf, width=Cm(16))
            continue
        if block == "table":
            cols = max(len(r) for r in data)
            table = d.add_table(rows=len(data), cols=cols, style="Table Grid")
            for r, row in enumerate(data):
                for c, value in enumerate(row):
                    run = table.cell(r, c).paragraphs[0].add_run(plain_line(value))
                    run.bold = True if r == 0 else None  # η πρώτη γραμμή είναι η επικεφαλίδα
            continue
        line = data
        if not line.strip():
            continue
        kind, text = line_kind(line.strip())
        if kind in ("#", "##", "###"):
            p = d.add_heading(level=len(kind))
        elif kind == "-":
            p = d.add_paragraph(style="List Bullet")
        else:
            p = d.add_paragraph()
        for part, style in inline_parts(text):
            run = p.add_run(part)
            run.bold = True if style == "b" else None
            if style == "code":
                run.font.name = "Consolas"
    d.save(path)


def export_xlsx(md, path):
    """Excel: κάθε γραμμή του κειμένου σε μία γραμμή του φύλλου, οι τίτλοι με έντονα."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font
    wb = Workbook()
    ws = wb.active
    ws.title = "XrysaStudy"
    ws.column_dimensions["A"].width = 110

    def add(values, kind="p"):
        ws.append(values)
        for c in range(1, len(values) + 1):
            cell = ws.cell(ws.max_row, c)
            cell.data_type = "s"  # μια γραμμή που ξεκινά με «=» να μείνει κείμενο και όχι τύπος του Excel
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            if kind in ("#", "##", "###", "th"):
                cell.font = Font(bold=True, size={"#": 16, "##": 13, "###": 12}.get(kind, 11))

    for block, data in parse_blocks(md):
        if block == "diagram":
            for k, line in enumerate(diagram_text(*data)):
                add([line], "###" if k == 0 else "p")
        elif block == "table":  # κάθε στήλη του πίνακα σε δική της στήλη του Excel
            for r, row in enumerate(data):
                add([plain_line(v) for v in row], "th" if r == 0 else "p")
        else:
            kind, text = line_kind(data.strip())
            add([("• " if kind == "-" else "") + plain_line(text)], kind)
    wb.save(path)


def export_txt(md, path):
    lines = []
    for block, data in parse_blocks(md):
        if block == "diagram":
            lines += diagram_text(*data)
        elif block == "table":
            lines += [" | ".join(plain_line(v) for v in row) for row in data]
        else:
            kind, text = line_kind(data.strip())
            lines.append(("• " if kind == "-" else "") + plain_line(text))
    with open(path, "w", encoding="utf-8-sig") as f:  # utf-8-sig: το Σημειωματάριο δείχνει σωστά τα ελληνικά
        f.write("\n".join(lines))


# είδος → (όνομα, κατάληξη, συνάρτηση, εικονίδιο)· το export_pdf ορίζεται πιο κάτω, γι' αυτό μπαίνει με όνομα
EXPORT_FORMATS = {"pdf": ("PDF", ".pdf", "export_pdf", "📕"), "docx": ("Word", ".docx", "export_docx", "📘"),
                  "xlsx": ("Excel", ".xlsx", "export_xlsx", "📗"), "txt": ("Κείμενο", ".txt", "export_txt", "📄")}


_ICON_FONT = []


def make_icon(ch, size, label=None):
    """Χρωματιστό εικονίδιο από τη γραμματοσειρά emoji των Windows (χωρίς αρχεία εικόνων).
    label: λέξη γραμμένη μέσα στο εικονίδιο (π.χ. «Chat» μέσα στο συννεφάκι)."""
    from PIL import Image, ImageDraw, ImageFont, ImageTk
    fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    if not _ICON_FONT:
        _ICON_FONT.append(ImageFont.truetype(os.path.join(fonts, "seguiemj.ttf"), 109))
    # Μεγάλος καμβάς και σχέδιο από αριστερά: τα emoji με «παραλλαγή χρώματος» (⚙️, ▶️) αλλιώς κόβονται στη μέση
    img = Image.new("RGBA", (320, 200), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((60, 100), ch, font=_ICON_FONT[0], embedded_color=True, anchor="lm")
    img = img.crop(img.getbbox() or (0, 0, 200, 200))
    side = max(img.size)  # τετράγωνο, ώστε το εικονίδιο να μην παραμορφώνεται
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
    if label:  # λίγο πάνω από το κέντρο: εκεί είναι το «σώμα» του συννεφιού
        font = ImageFont.truetype(os.path.join(fonts, "segoeuib.ttf"), int(side * 0.26))
        ImageDraw.Draw(square).text((side * 0.5, side * 0.44), label, font=font, fill=ACCENT, anchor="mm")
    return ImageTk.PhotoImage(square.resize((size, size), Image.LANCZOS))


def export_pdf(md, path):
    """Μετατρέπει το κείμενο της οθόνης σε PDF με ελληνικά."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    # Οι γραμματοσειρές των Windows έχουν ελληνικά· οι ενσωματωμένες του reportlab όχι
    fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    pdfmetrics.registerFont(TTFont("Arial", os.path.join(fonts, "arial.ttf")))
    pdfmetrics.registerFont(TTFont("Arial-Bold", os.path.join(fonts, "arialbd.ttf")))
    pdfmetrics.registerFont(TTFont("Consolas", os.path.join(fonts, "consola.ttf")))
    pdfmetrics.registerFontFamily("Arial", normal="Arial", bold="Arial-Bold", italic="Arial", boldItalic="Arial-Bold")

    def style(name, size, bold=False, before=4, indent=0):
        return ParagraphStyle(name, fontName="Arial-Bold" if bold else "Arial", fontSize=size,
                              leading=size * 1.35, spaceBefore=before, spaceAfter=3, leftIndent=indent)

    styles = {"#": style("h1", 18, True, 0), "##": style("h2", 14, True, 12),
              "###": style("h3", 12, True, 8), "-": style("li", 11, indent=14), "p": style("p", 11)}

    from reportlab.lib import colors
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import Image as PdfImage, Table, TableStyle

    story = []
    for block, data in parse_blocks(md):
        if block == "diagram":
            img = draw_diagram(*data)
            width = min(17 * cm, img.width / 2 * 0.75)  # η εικόνα είναι σε διπλό μέγεθος· 0.75 = pixels → points
            buf = io.BytesIO()
            img.save(buf, "PNG")
            buf.seek(0)
            story += [Spacer(1, 6), PdfImage(buf, width=width, height=width * img.height / img.width), Spacer(1, 6)]
            continue
        if block == "table":
            cols = max(len(r) for r in data)
            cells = [[Paragraph(inline_html(v), styles["p"]) for v in row + [""] * (cols - len(row))] for row in data]
            table = Table(cells, colWidths=[17 * cm / cols] * cols, repeatRows=1)
            table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9aa5b1")),
                                       ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
                                       ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story += [Spacer(1, 6), table, Spacer(1, 6)]
            continue
        line = data.strip()
        if not line:
            story.append(Spacer(1, 4))
            continue
        kind, text = line_kind(line)
        if kind == "-":
            story.append(Paragraph(inline_html(text), styles["-"], bulletText="•"))
        else:
            story.append(Paragraph(inline_html(text), styles[kind]))
    SimpleDocTemplate(path, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                      topMargin=2 * cm, bottomMargin=2 * cm).build(story)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.folders = ensure_folders(os.path.join(documents_dir(), "XrysaStudy"))
        self.kinds = {}          # από ποιο section βγήκε το κείμενο κάθε καρτέλας (για τον φάκελο εξαγωγής)
        self.icons = {}          # τα εικονίδια πρέπει να μένουν κάπου, αλλιώς το Tk τα «ξεχνά» και εξαφανίζονται
        self.editing = None      # ποια καρτέλα επεξεργάζεσαι χειροκίνητα αυτή τη στιγμή
        # Αρχεία κάθε section (μόνο όσα υπάρχουν ακόμα στον δίσκο)
        self.files = {k: [p for p in self.cfg["files"][k] if os.path.exists(p)] for k in SECTIONS}
        self.only = {k: tk.BooleanVar(value=self.cfg["only"][k]) for k in SECTIONS}
        self.boxes, self.lists, self.panels, self.section_btns = {}, {}, {}, {}
        self.section = None      # ποιο section είναι ανοιχτό
        self.level = tk.StringVar(value="simple")
        self.official = tk.BooleanVar(value=self.cfg["official"])
        self.autoproof = tk.BooleanVar(value=self.cfg["autoproof"])
        self.jobs = {}           # τι τρέχει σε κάθε καρτέλα: "doc" (νέο αποτέλεσμα) ή "rewrite" (ανθρώπινο/ορθογραφία)
        self.sources = {}        # τα επιστημονικά άρθρα που βρέθηκαν για την εργασία κάθε καρτέλας
        self.edit_tab = None     # σε ποια καρτέλα εφαρμόζονται οι αλλαγές που ετοιμάζονται
        self.edit_reply = ""
        self.orig_reply = ""
        self.orig_ctx = None     # αποτελέσματα του τοπικού ελέγχου πρωτοτυπίας, μέχρι να απαντήσει το Claude
        self.out = {p: "" for p in PROVIDERS}       # το κείμενο κάθε καρτέλας
        self.names = {p: "βοήθημα" for p in PROVIDERS}
        self.backup = {}         # το κείμενο πριν το «Πιο ανθρώπινο», για το «Αρχικό»
        self.tab = "Claude"
        self.chat_history = []
        self.chat_reply = ""
        self.size = 11
        self.q = queue.Queue()
        self.busy = set()        # ποιες καρτέλες (ή το chat) περιμένουν απάντηση

        self.detachables, self.detach_btns = {}, {}  # πλαίσια που βγαίνουν σε ξεχωριστό παράθυρο
        self.detached = set()
        self.chat_open = False

        # «Μέγεθος εμφάνισης»: μεγαλώνει/μικραίνει όλο το πρόγραμμα (γράμματα, κουμπιά, εικονίδια) μαζί
        self.base_scaling = float(self.tk.call("tk", "scaling"))
        self.tk.call("tk", "scaling", self.base_scaling * self.cfg.get("zoom", 1.0))

        self.title("XrysaStudy")
        try:
            self.iconbitmap(os.path.join(APP_DIR, "xrysastudy.ico"))  # το 📚 στη γραμμή τίτλου και στη γραμμή εργασιών
        except tk.TclError:
            pass
        self.configure(bg=BG)
        self._restore_window()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._bind_editing()

        self._build_top()
        tk.Label(self, text=f"XrysaStudy έκδοση {VERSION}", bg=BG, fg=MUTED, font=("Segoe UI", 8)).pack(side="bottom", anchor="w", padx=10, pady=(0, 6))
        # Οι στήλες χωρίζονται με διαχωριστικά που σέρνονται με το ποντίκι
        self.body = tk.PanedWindow(self, orient="horizontal", bg="#d9d9d9", sashwidth=6, bd=0, sashcursor="sb_h_double_arrow")
        self.body.pack(fill="both", expand=True, padx=10, pady=6)
        self._build_side(self.body)
        for key in SECTIONS:
            self._build_panel(self.body, key)
        self._build_chat(self.body)
        self._build_right(self.body)

        self._tick()
        self._poll()
        self.after(3000, self.check_updates)  # αθόρυβος έλεγχος για νέα έκδοση λίγο μετά το άνοιγμα
        if "zoom" not in self.cfg:  # πρώτο άνοιγμα σε αυτόν τον υπολογιστή: πρόταση μεγέθους για την οθόνη του
            self.after(1500, self.first_run_zoom)

    # ---------- αντιγραφή / επικόλληση ----------
    def _bind_editing(self):
        """Δεξί κλικ και Ctrl+C/V/X/A σε όλα τα κουτιά κειμένου του προγράμματος."""
        for cls in ("Entry", "Text"):
            self.bind_class(cls, "<Button-3>", self._context_menu)
            self.bind_class(cls, "<Control-KeyPress>", self._ctrl_key, add="+")
            for seq in ("<Control-a>", "<Control-A>"):
                self.bind_class(cls, seq, lambda e: self._select_all(e.widget) or "break")

    def _ctrl_key(self, e):
        # Με ελληνικό πληκτρολόγιο το Tk δεν καταλαβαίνει το Ctrl+Ψ ως Ctrl+C· το βρίσκουμε από το φυσικό πλήκτρο
        if e.keycode == 65:  # A
            self._select_all(e.widget)
            return "break"
        action = {67: "<<Copy>>", 86: "<<Paste>>", 88: "<<Cut>>"}.get(e.keycode)
        if action and e.keysym.lower() not in ("c", "v", "x"):  # με λατινικό πληκτρολόγιο τα χειρίζεται ήδη το Tk
            e.widget.event_generate(action)
            return "break"

    def _select_all(self, w):
        if isinstance(w, tk.Entry):
            w.select_range(0, "end")
            w.icursor("end")
        else:
            w.tag_add("sel", "1.0", "end-1c")

    def _edit_menu(self, w):
        """Το μενού του δεξιού κλικ· στα κουτιά που μόνο διαβάζονται (αποτέλεσμα, ιστορικό chat) μόνο αντιγραφή."""
        state = "normal" if str(w.cget("state")) != "disabled" else "disabled"
        m = tk.Menu(self, tearoff=0, font=("Segoe UI", 10))
        m.add_command(label="Αποκοπή", accelerator="Ctrl+X", state=state, command=lambda: w.event_generate("<<Cut>>"))
        m.add_command(label="Αντιγραφή", accelerator="Ctrl+C", command=lambda: w.event_generate("<<Copy>>"))
        m.add_command(label="Επικόλληση", accelerator="Ctrl+V", state=state, command=lambda: w.event_generate("<<Paste>>"))
        m.add_command(label="Διαγραφή", state=state, command=lambda: w.event_generate("<<Clear>>"))
        m.add_separator()
        m.add_command(label="Επιλογή όλων", accelerator="Ctrl+A", command=lambda: self._select_all(w))
        return m

    def _context_menu(self, e):
        e.widget.focus_set()
        self._edit_menu(e.widget).tk_popup(e.x_root, e.y_root)

    # ---------- κομμάτια του παραθύρου ----------
    def icon(self, ch, size, label=None):
        """size σε «κανονικά» pixels· μεγαλώνει μαζί με τη μεγέθυνση της οθόνης και το «Μέγεθος εμφάνισης»."""
        if (ch, size, label) not in self.icons:
            try:
                self.icons[ch, size, label] = make_icon(ch, round(size * self.winfo_fpixels("1i") / 96), label)
            except Exception:
                self.icons[ch, size, label] = None  # χωρίς τη γραμματοσειρά emoji το κουμπί δείχνει μόνο κείμενο
        return self.icons[ch, size, label]

    def _button(self, parent, text, cmd, big=False, icon=None, top=False, **kw):
        """Κουμπί σε στυλ PharmDesk· icon = χρωματιστό εικονίδιο, top = εικονίδιο πάνω από το κείμενο."""
        img = self.icon(icon, 34 if top else 16) if icon else None
        return tk.Button(parent, text=text if top or not img else " " + text, command=cmd, bg=PANEL, fg=TEXT,
                         activebackground="#e5f0fb", relief="flat", bd=0, highlightthickness=1,
                         highlightbackground=BORDER, font=BOLD, cursor="hand2", padx=8, pady=6 if big else 3,
                         image=img or "", compound=("top" if top else "left") if img else "none", **kw)

    def _labelframe(self, parent, text, icon, detach=None, **kw):
        """Πλαίσιο με τίτλο και χρωματιστό εικονίδιο, όπως στο PharmDesk.
        detach: όνομα για το κουμπί «Παράθυρο», που βγάζει το πλαίσιο σε ξεχωριστό παράθυρο των Windows."""
        if detach:
            # Το Tk 9 βγάζει σε ξεχωριστό παράθυρο μόνο απλό Frame (όχι LabelFrame)· γι' αυτό το «κουτί» holder
            holder = tk.Frame(parent, bg=BG)
            lf = tk.LabelFrame(holder, bg=BG, **kw)
            lf.pack(fill="both", expand=True)
        else:
            lf = tk.LabelFrame(parent, bg=BG, **kw)
        head = tk.Frame(lf, bg=BG)
        tk.Label(head, text=f" {text} ", image=self.icon(icon, 16) or "", compound="left", bg=BG, fg=TEXT,
                 font=BOLD if detach else FONT).pack(side="left")
        if detach:
            b = tk.Button(head, command=lambda: self.toggle_detach(detach), bg=BG, fg=ACCENT, relief="flat", bd=0,
                          font=("Segoe UI", 8, "bold"), cursor="hand2", padx=4, pady=0, activebackground="#e5f0fb")
            b.pack(side="left", padx=(6, 0))
            self.detach_btns[detach], self.detachables[detach] = b, holder
            self._detach_label(detach)
        lf.config(labelwidget=head)
        return lf

    def _detach_label(self, key):
        out = key in self.detached
        self.detach_btns[key].config(text=" Επιστροφή" if out else " Παράθυρο",
                                     image=self.icon("📌" if out else "🪟", 13) or "", compound="left")

    def _textbox(self, parent, **kw):
        return tk.Text(parent, bg=PANEL, fg=TEXT, relief="flat", wrap="word", font=FONT,
                       highlightthickness=1, highlightbackground=BORDER, padx=6, pady=4, **kw)

    def _build_top(self):
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=10, pady=(8, 0))
        logo = self.icon("📚", 26)
        tk.Label(top, text="  XrysaStudy", image=logo or "", compound="left", bg=BG, fg=TEXT,
                 font=("Segoe UI", 13, "bold")).pack(side="left")
        self._button(top, "Ρυθμίσεις", self.settings, icon="⚙️").pack(side="left", padx=(16, 4))
        self._button(top, "Οι φάκελοί μου", lambda: os.startfile(self.folders["base"]), icon="📂").pack(side="left", padx=4)
        self.clock = tk.Label(top, bg=BG, fg=TEXT, font=BOLD)
        self.clock.pack(side="right")

        # Κόστος (με «Μηδενισμό») και Κατάσταση: μικρές γραμμές στην πάνω μπάρα, για να μένει χώρος στο Αποτέλεσμα
        cost = tk.Frame(top, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        cost.pack(side="right", padx=(8, 12))
        tk.Label(cost, image=self.icon("💰", 16) or "", bg=PANEL).pack(side="left", padx=(4, 0))
        self.cost_label = tk.Label(cost, bg=PANEL, fg=TEXT, font=("Segoe UI", 8), padx=4, pady=3)
        self.cost_label.pack(side="left")
        reset = self._button(cost, "Μηδενισμός", self.reset_cost, icon="🔄")
        reset.config(font=("Segoe UI", 8, "bold"))
        reset.pack(side="left")
        add_cost(self.cfg["costs"], 0.0, datetime.date.today())  # μηδενίζει αν άλλαξε μέρα/μήνας από την τελευταία φορά
        self.show_cost()

        self.status = tk.Label(top, text="Διάλεξε «Βοήθημα», «Άσκηση» ή «Εργασία».", bg=PANEL, fg=MUTED, font=FONT,
                               anchor="w", padx=6, pady=4, image=self.icon("ℹ️", 16) or "", compound="left",
                               highlightthickness=1, highlightbackground=BORDER)
        self.status.pack(side="left", fill="x", expand=True, padx=(8, 0))

    def _side_button(self, parent, text, cmd, icon, label=None):
        """Μεγάλο κουμπί της αριστερής στήλης: εικονίδιο αριστερά και η λέξη δίπλα του, στο ίδιο κουτί."""
        img = self.icon(icon, 46 if label else 34, label)
        caption = ("  " + text if text else "") if img else (text or label)  # με εικονίδιο, το label είναι ήδη μέσα του
        return tk.Button(parent, text=caption, image=img or "",
                         compound="left" if img else "none", anchor="center" if label else "w", command=cmd,
                         bg=PANEL, fg=TEXT, activebackground="#e5f0fb", relief="flat", bd=0, highlightthickness=1,
                         highlightbackground=BORDER, font=("Segoe UI", 11, "bold"), cursor="hand2",
                         padx=12, pady=2 if label else 6)

    def _build_side(self, body):
        """Στενή αριστερή στήλη με τα κουμπιά το ένα κάτω από το άλλο, για να μένει πλάτος για το κείμενο."""
        side = self.side = tk.Frame(body, bg=BG)
        body.add(side, width=self.pane_width("side", "5.6c"), minsize=self.winfo_pixels("3c"), stretch="never")
        for key, title in SECTIONS.items():
            b = self._side_button(side, title, lambda k=key: self.toggle_section(k), SECTION_ICONS[key])
            b.pack(fill="x", pady=3)
            self.section_btns[key] = b
        self.chat_btn = self._side_button(side, "", self.toggle_chat, "💬", label="Chat")
        self.chat_btn.pack(fill="x", pady=3)
        self.export_btn = self._side_button(side, "Εξαγωγή", self.export_menu, "💾")
        self.export_btn.pack(fill="x", pady=3)
        self._side_button(side, "Εκτύπωση", self.print_pdf, "🖨️").pack(fill="x", pady=3)

    def _build_chat(self, body):
        """Πλαίσιο chat: ερωτήσεις κατευθείαν στο Claude, με βάση ό,τι έχει φορτωθεί. Ανοίγει με το κουμπί «Chat»."""
        chat = self.chat_panel = self._labelframe(body, "Chat", "💬", detach="chat")
        self.chat_view = self._textbox(chat, height=6, state="disabled")
        self.chat_view.pack(fill="both", expand=True, padx=4, pady=(4, 2))
        self.chat_view.tag_config("me", font=BOLD, foreground=ACCENT, spacing1=6)
        self.chat_view.tag_config("bot", font=BOLD, spacing1=6)
        row = tk.Frame(chat, bg=BG)
        row.pack(fill="x", padx=4, pady=(2, 4))
        self.chat_entry = tk.Entry(row, font=("Segoe UI", 10), relief="flat", highlightthickness=1,
                                   highlightbackground=BORDER)
        self.chat_entry.pack(side="left", fill="x", expand=True, ipady=4)
        self.chat_entry.bind("<Return>", lambda e: self.send_chat())
        self._button(row, "Αποστολή", self.send_chat, icon="💬").pack(side="left", padx=(4, 0))

    def _build_panel(self, body, key):
        """Πλαίσιο ενός section (Βοήθημα / Άσκηση / Εργασία) δίπλα στο λευκό πεδίο."""
        p = self.panels[key] = self._labelframe(body, SECTIONS[key], SECTION_ICONS[key], detach=key)
        action = {"study": ("Φτιάξε βοήθημα", "Τι θέλεις να κάνω; (προαιρετικό)"),
                  "exercise": ("Λύσε την άσκηση", "Εκφώνηση (γράψε ή επικόλλησε):"),
                  "essay": ("Φτιάξε εργασία", "Θέμα και οδηγίες της εργασίας:")}[key]

        # Από κάτω προς τα πάνω: τα κουμπιά μένουν πάντα ορατά και «μαζεύεται» μόνο το κουτί κειμένου
        self._button(p, "Κλείσιμο", lambda: self.toggle_section(key), icon="❌").pack(side="bottom", fill="x", padx=6, pady=(0, 6))
        self._button(p, action[0], lambda: self.run_section("Claude", key), big=True, icon="🚀").pack(side="bottom", fill="x", padx=6, pady=(10, 4))
        if key == "essay":
            # Μορφή παραπομπών: έτοιμες μορφές ή δικό μου παράδειγμα
            from tkinter import ttk
            cite = tk.Frame(p, bg=BG)
            cite.pack(side="bottom", fill="x", padx=6, pady=(2, 0))
            self.cite_label = tk.Label(cite, text="Μορφή παραπομπών:", bg=BG, fg=TEXT, font=BOLD)
            self.cite_label.pack(side="left")
            self.cite_style = tk.StringVar(value=self.cfg["citation_style"])
            box = ttk.Combobox(cite, textvariable=self.cite_style, state="readonly", font=FONT,
                               values=list(CITATION_STYLES) + [CUSTOM_STYLE])
            box.pack(side="left", fill="x", expand=True, padx=(6, 0))
            box.bind("<<ComboboxSelected>>", lambda e: self.choose_citation())
            tk.Checkbutton(p, text="Από επίσημες πηγές (PubMed, OpenAlex)", variable=self.official,
                           bg=BG, activebackground=BG, font=BOLD, cursor="hand2",
                           command=self._official_changed).pack(side="bottom", anchor="w", padx=4)
            self.cite_label.config(bg="#fff3a3" if self.official.get() else BG)
        tk.Checkbutton(p, text="Απάντα μόνο από αυτά τα αρχεία", variable=self.only[key], bg=BG, activebackground=BG,
                       font=BOLD, cursor="hand2", command=self._save_files).pack(side="bottom", anchor="w", padx=4)
        row = tk.Frame(p, bg=BG)
        row.pack(side="bottom", fill="x", padx=6)
        self._button(row, "Φόρτωση αρχείων", lambda: self.add_files(key), icon="➕").pack(side="left", fill="x", expand=True)
        self._button(row, "Αφαίρεση", lambda: self.remove_files(key), icon="➖").pack(side="left", padx=(4, 0))
        lst = self.lists[key] = tk.Listbox(p, bg=PANEL, fg=TEXT, font=FONT, relief="flat", height=5, highlightthickness=1,
                                           highlightbackground=BORDER, selectbackground=ACCENT, activestyle="none",
                                           selectmode="extended")
        lst.pack(side="bottom", fill="x", padx=6, pady=2)
        for path in self.files[key]:
            lst.insert("end", os.path.basename(path))
        files_label = {"study": "Αρχεία για το βοήθημα (PDF, Word, PowerPoint…):",
                       "exercise": "Αρχεία: σημειώσεις και δεδομένα (Excel, Access…):",
                       "essay": "Αρχεία / πηγές για την εργασία:"}[key]
        tk.Label(p, text=files_label, bg=BG, fg=TEXT, font=BOLD).pack(side="bottom", anchor="w", padx=6, pady=(8, 0))

        if key == "study":
            levels = tk.Frame(p, bg=BG)
            levels.pack(side="bottom", fill="x", padx=6, pady=(6, 0))
            tk.Label(levels, text="Είδος:", bg=BG, fg=TEXT, font=BOLD).pack(side="left")
            for value, label in (("simple", "Απλό"), ("detailed", "Αναλυτικό")):
                tk.Radiobutton(levels, text=label, value=value, variable=self.level, bg=BG, activebackground=BG,
                               font=BOLD, cursor="hand2").pack(side="left", padx=(8, 0))
        if key == "exercise":
            self._button(p, "Φόρτωση εκφώνησης από αρχείο", self.load_statement, icon="📄").pack(side="bottom", fill="x", padx=6, pady=(2, 0))

        tk.Label(p, text=action[1], bg=BG, fg=TEXT, font=BOLD).pack(anchor="w", padx=6, pady=(4, 0))
        self.boxes[key] = self._textbox(p, height=6)
        self.boxes[key].pack(fill="both", expand=True, padx=6, pady=2)

    def _build_right(self, body):
        # Δεξιά: το «Αποτέλεσμα» (μέσα σε PanedWindow, ώστε να βγαίνει και να ξαναμπαίνει με «Παράθυρο»)
        right = self.right = tk.PanedWindow(body, orient="vertical", bg="#d9d9d9", sashwidth=6, bd=0,
                                            sashcursor="sb_v_double_arrow")
        body.add(right, minsize=self.winfo_pixels("8c"), stretch="always")

        view = self._labelframe(right, "Αποτέλεσμα", "📄", detach="result")
        right.add(self.detachables["result"], stretch="always", minsize=self.winfo_pixels("5c"))

        # Γραμμή 1: καρτέλες και μέγεθος γραμμάτων
        bar = tk.Frame(view, bg=BG)
        bar.pack(fill="x", padx=4, pady=(4, 2))
        self.tab_btns = {}
        for name in PROVIDERS:
            b = self._button(bar, name, lambda n=name: self.show_tab(n))
            b.pack(side="left", padx=(0, 2))
            self.tab_btns[name] = b
        self._button(bar, "+", lambda: self.zoom(1)).pack(side="right")
        self.size_label = tk.Label(bar, bg=BG, fg=TEXT, font=BOLD, width=3)
        self.size_label.pack(side="right")
        self._button(bar, "−", lambda: self.zoom(-1)).pack(side="right")
        tk.Label(bar, text="Γράμματα:", bg=BG, fg=TEXT, font=BOLD).pack(side="right", padx=(0, 4))

        # Γραμμή 2: δεύτερη γνώμη και τι θα συνδυάσει το Claude
        bar2 = tk.Frame(view, bg=BG)
        bar2.pack(fill="x", padx=4, pady=(2, 4))
        tk.Label(bar2, text="Δεύτερη γνώμη:", bg=BG, fg=TEXT, font=BOLD).pack(side="left")
        self.opinion_btns = {}
        for name in ("Gemini", "ChatGPT"):
            b = self._button(bar2, name, lambda n=name: self.opinion(n), icon="▶️")
            b.pack(side="left", padx=(4, 0))
            self.opinion_btns[name] = b
        tk.Label(bar2, text="Συνδύασε:", bg=BG, fg=TEXT, font=BOLD).pack(side="left", padx=(18, 0))
        self.include = {n: tk.BooleanVar() for n in ("Gemini", "ChatGPT")}
        self.include_boxes = {}
        for name, var in self.include.items():
            c = tk.Checkbutton(bar2, text=name, variable=var, bg=BG, activebackground=BG, font=BOLD, cursor="hand2")
            c.pack(side="left", padx=(4, 0))
            self.include_boxes[name] = c

        # Γραμμή 3: επεξεργασία του κειμένου (ύφος, ορθογραφία, επαναφορά)
        bar3 = tk.Frame(view, bg=BG)
        bar3.pack(fill="x", padx=4, pady=(0, 4))
        self._button(bar3, "Πιο ανθρώπινο", self.humanize, icon="🪄").pack(side="left")
        self._button(bar3, "Ορθογραφία", self.proofread, icon="✅").pack(side="left", padx=(4, 0))
        tk.Checkbutton(bar3, text="Αυτόματα", variable=self.autoproof, bg=BG, activebackground=BG,
                       font=BOLD, cursor="hand2", command=self._save_files).pack(side="left", padx=(4, 0))
        self._button(bar3, "Πρωτοτυπία", self.check_originality, icon="🔍").pack(side="left", padx=(8, 0))
        self._button(bar3, "Αρχικό", self.undo_humanize, icon="↩️").pack(side="left", padx=(8, 0))

        # Γραμμή 4: αλλαγές με οδηγίες στο Claude, ή χειροκίνητα μέσα στο κείμενο
        bar4 = tk.Frame(view, bg=BG)
        bar4.pack(fill="x", padx=4, pady=(0, 4))
        tk.Label(bar4, text="Αλλαγές:", image=self.icon("🖊️", 16) or "", compound="left",
                 bg=BG, fg=TEXT, font=BOLD).pack(side="left")
        self.edit_entry = tk.Entry(bar4, font=("Segoe UI", 10), relief="flat", highlightthickness=1,
                                   highlightbackground=BORDER)
        self.edit_entry.pack(side="left", fill="x", expand=True, padx=(6, 4), ipady=4)
        self.edit_entry.bind("<Return>", lambda e: self.request_edit())
        self._button(bar4, "Εφάρμοσε", self.request_edit, icon="📤").pack(side="left")
        self.manual_btn = self._button(bar4, "Επεξεργασία", self.toggle_manual, icon="✏️")
        self.manual_btn.pack(side="left", padx=(8, 0))

        frame = tk.Frame(view, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        frame.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        scroll = tk.Scrollbar(frame)
        scroll.pack(side="right", fill="y")
        self.text = tk.Text(frame, bg=PANEL, fg=TEXT, relief="flat", wrap="word", padx=14, pady=10,
                            yscrollcommand=scroll.set, state="disabled", undo=True)  # undo: Ctrl+Z στη χειροκίνητη επεξεργασία
        self.text.pack(fill="both", expand=True)
        scroll.config(command=self.text.yview)
        self.zoom(0)
        self.show_tab("Claude")
        self.refresh_providers()

    def refresh_providers(self):
        """Το ChatGPT μένει γκρι όσο δεν υπάρχει κλειδί του (θέλει πληρωμένο API)."""
        on = bool(self.cfg["keys"].get("ChatGPT") or os.environ.get(KEY_ENV["ChatGPT"]))
        state = "normal" if on else "disabled"
        for w in (self.tab_btns["ChatGPT"], self.opinion_btns["ChatGPT"], self.include_boxes["ChatGPT"]):
            w.config(state=state)
        if not on:
            self.include["ChatGPT"].set(False)
            if self.tab == "ChatGPT":
                self.show_tab("Claude")

    # ---------- γενικά ----------
    def _tick(self):
        days = ["Δευ", "Τρί", "Τετ", "Πέμ", "Παρ", "Σάβ", "Κυρ"]  # σύντομα, για να χωρά η Κατάσταση στην πάνω μπάρα
        now = datetime.datetime.now()
        self.clock.config(text=f"{days[now.weekday()]} {now:%d/%m/%Y}  {now:%H:%M}")
        self.after(1000, self._tick)

    def set_status(self, msg, color=MUTED):
        self.status.config(text=msg, fg=color)

    def show_cost(self):
        c = self.cfg["costs"]
        parts = [(label, c.get(money_key, 0.0), c.get(tokens_key, 0)) for label, money_key, tokens_key in
                 (("Τελευταίο", "last", "last_tokens"), ("Σήμερα", "today", "today_tokens"),
                  ("Μήνας", "month_total", "month_tokens"))]
        self.cost_label.config(text=" · ".join(f"{label} {money(m)} ({count_fmt(t)})" for label, m, t in parts))

    def reset_cost(self):
        """«Μηδενισμός»: τελευταίο, σήμερα και μήνας ξεκινούν από το 0 (ρωτά πρώτα)."""
        if not messagebox.askyesno("Μηδενισμός κόστους", "Να μηδενιστούν το κόστος και τα tokens "
                                                         "(τελευταίο, σήμερα και μήνας);"):
            return
        self.cfg["costs"] = add_cost({}, 0.0, datetime.date.today())
        save_config(self.cfg)
        self.show_cost()
        self.set_status("Το κόστος μηδενίστηκε.", "green")

    def zoom(self, step):
        self.size = max(8, min(24, self.size + step))
        s = self.size
        self.size_label.config(text=str(s))
        self.text.config(font=("Segoe UI", s))
        self.text.tag_config("#", font=("Segoe UI", s + 7, "bold"), spacing1=4, spacing3=6)
        self.text.tag_config("##", font=("Segoe UI", s + 3, "bold"), foreground=ACCENT, spacing1=12, spacing3=4)
        self.text.tag_config("###", font=("Segoe UI", s + 1, "bold"), spacing1=8, spacing3=2)
        self.text.tag_config("-", lmargin1=12, lmargin2=26, spacing3=2)
        self.text.tag_config("p", spacing3=2)
        self.text.tag_config("b", font=("Segoe UI", s, "bold"))
        self.text.tag_config("code", font=("Consolas", s), background="#eef3fb")
        self.text.tag_config("muted", foreground=MUTED, justify="center")
        self.text.tag_config("changed", background="#fff3a3")  # σημεία που άλλαξαν με το «✏ Αλλαγές»
        self.text.tag_config("th", font=("Segoe UI", s, "bold"), background="#dbeafe")  # επικεφαλίδα πίνακα
        self.text.tag_config("copied", background="#ffc9c9")   # αυτούσια ίδιο με πηγή (έλεγχος πρωτοτυπίας)
        self.text.tag_config("close", background="#ffe0b2")    # πολύ κοντινή απόδοση/μετάφραση πηγής

    def settings(self):
        win = tk.Toplevel(self, bg=BG, padx=14, pady=12)
        win.title("Ρυθμίσεις")
        win.transient(self)
        win.grab_set()
        for col, head in enumerate(("Υπηρεσία", "Κλειδί API", "Μοντέλο", "Πού βρίσκω το κλειδί")):
            tk.Label(win, text=head, bg=BG, fg=TEXT, font=BOLD).grid(row=0, column=col, sticky="w", padx=4, pady=(0, 6))
        fields = {}
        for r, name in enumerate(PROVIDERS, 1):
            tk.Label(win, text=name, bg=BG, fg=TEXT, font=BOLD).grid(row=r, column=0, sticky="w", padx=4, pady=3)
            key = tk.Entry(win, width=42, show="•", font=FONT)
            key.insert(0, self.cfg["keys"].get(name, ""))
            key.grid(row=r, column=1, padx=4, ipady=3)
            model = tk.Entry(win, width=24, font=FONT)
            model.insert(0, self.cfg["models"][name])
            model.grid(row=r, column=2, padx=4, ipady=3)
            site = KEY_SITE[name] + ("  (πληρωμένο, προαιρετικό)" if name == "ChatGPT" else "")
            tk.Label(win, text=site, bg=BG, fg=MUTED, font=FONT).grid(row=r, column=3, sticky="w", padx=4)
            fields[name] = (key, model)

        tk.Label(win, text="Μόνιμες οδηγίες (ισχύουν σε βοήθημα, άσκηση, εργασία και chat):", bg=BG, fg=TEXT,
                 font=BOLD).grid(row=4, column=0, columnspan=4, sticky="w", padx=4, pady=(14, 2))
        instr = self._textbox(win, height=6, width=90)
        instr.insert("1.0", self.cfg["instructions"])
        instr.grid(row=5, column=0, columnspan=4, sticky="ew", padx=4)
        tk.Label(win, text="π.χ. «Στο Excel λύνε με συναρτήσεις όπως στις σημειώσεις του καθηγητή, όχι με μενού.»",
                 bg=BG, fg=MUTED, font=FONT).grid(row=6, column=0, columnspan=4, sticky="w", padx=4)

        zoom_row = tk.Frame(win, bg=BG)
        zoom_row.grid(row=7, column=0, columnspan=4, sticky="ew", padx=4, pady=(14, 0))
        tk.Label(zoom_row, text="Μέγεθος εμφάνισης:", image=self.icon("🔎", 16) or "", compound="left",
                 bg=BG, fg=TEXT, font=BOLD).pack(side="left")
        zoom = tk.StringVar(value=f"{round(self.cfg.get('zoom', 1.0) * 100)}%")
        tk.Spinbox(zoom_row, values=[f"{p}%" for p in range(70, 155, 5)], textvariable=zoom, width=6,
                   font=FONT, state="readonly").pack(side="left", padx=6)
        zoom_info = tk.Label(zoom_row, text="", bg=BG, fg=MUTED, font=FONT)

        def auto_zoom():
            z, screen = self.suggest_zoom()
            zoom.set(f"{round(z * 100)}%")
            zoom_info.config(text=f"{screen} → προτείνω {round(z * 100)}%")
        self._button(zoom_row, "Αυτόματος εντοπισμός", auto_zoom, icon="🖥️").pack(side="left", padx=(4, 8))
        zoom_info.pack(side="left")

        def save():
            for name, (key, model) in fields.items():
                self.cfg["keys"][name] = key.get().strip()
                self.cfg["models"][name] = model.get().strip() or DEFAULT_MODELS[name]
            self.cfg["instructions"] = instr.get("1.0", "end").strip()
            new_zoom = int(zoom.get().rstrip("%")) / 100
            zoom_changed = abs(new_zoom - self.cfg.get("zoom", 1.0)) > 0.001
            self.cfg["zoom"] = new_zoom
            save_config(self.cfg)
            self.refresh_providers()
            win.destroy()
            self.set_status("Οι ρυθμίσεις αποθηκεύτηκαν.", "green")
            if zoom_changed:
                self.ask_restart()

        self._button(win, "Αποθήκευση", save, big=True, icon="💾").grid(row=8, column=0, columnspan=4, sticky="ew", pady=(12, 0))
        extra = tk.Frame(win, bg=BG)
        extra.grid(row=9, column=0, columnspan=4, sticky="ew", pady=(8, 0))
        self._button(extra, "Σχετικά (τι νέο έχει κάθε έκδοση)", self.about, icon="ℹ️").pack(side="left", expand=True, fill="x", padx=(0, 3))
        self._button(extra, "Έλεγχος για αναβάθμιση", lambda: self.check_updates(manual=True), icon="🔄").pack(
            side="left", expand=True, fill="x", padx=(3, 0))

    # ---------- μέγεθος εμφάνισης και παράθυρο ----------
    def suggest_zoom(self):
        """Προτεινόμενο «Μέγεθος εμφάνισης» για την οθόνη: (ποσοστό, περιγραφή οθόνης).
        Το πρόγραμμα σχεδιάστηκε για «χώρο» 1280×720 (π.χ. 1920×1080 με μεγέθυνση Windows 150%)."""
        windows_scale = self.base_scaling * 72 / 96  # η μεγέθυνση των Windows (1.0 = 100%)
        w, h = self.winfo_screenwidth(), self.winfo_screenheight()
        fit = min(w / windows_scale / 1280, h / windows_scale / 720)
        zoom = max(0.7, min(1.3, round(fit * 20) / 20))  # σε βήματα του 5%
        return zoom, f"Οθόνη {w}×{h}, μεγέθυνση Windows {round(windows_scale * 100)}%"

    def first_run_zoom(self):
        """Πρώτο άνοιγμα σε αυτόν τον υπολογιστή: προτείνει μέγεθος που χωράει όμορφα στην οθόνη του."""
        zoom, screen = self.suggest_zoom()
        self.cfg["zoom"] = 1.0
        save_config(self.cfg)
        if abs(zoom - 1.0) > 0.001 and messagebox.askyesno(
                "Μέγεθος εμφάνισης", f"{screen}.\nΠροτείνω μέγεθος εμφάνισης {round(zoom * 100)}% για να χωράει "
                                     "όμορφα το πρόγραμμα.\nΝα εφαρμοστεί; (Θα ξανανοίξει μόνο του.)\n\n"
                                     "Μπορείς να το αλλάξεις όποτε θέλεις από τις Ρυθμίσεις."):
            self.cfg["zoom"] = zoom
            save_config(self.cfg)
            self.restart()

    def ask_restart(self):
        if messagebox.askyesno("Μέγεθος εμφάνισης", "Το νέο μέγεθος εφαρμόζεται με επανεκκίνηση του προγράμματος.\n"
                                                    "Να γίνει τώρα; Τα κείμενα που δεν έχεις αποθηκεύσει θα χαθούν."):
            self.restart()

    def restart(self):
        self.cfg.pop("panes", None)  # τα πλάτη άλλαξαν μαζί με το μέγεθος· ξεκινάμε από τα προεπιλεγμένα
        self.on_close(restart=True)

    def _restore_window(self):
        """Ανοίγει με το μέγεθος και τη θέση που είχε το παράθυρο την τελευταία φορά."""
        win = self.cfg.get("window", {})
        geometry = win.get("geometry") or "1320x720+40+40"  # «or»: μπορεί να έχει αποθηκευτεί κενό (None)
        m = re.match(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", geometry)
        if m:  # να μη βγει εκτός οθόνης (π.χ. αν αποσυνδέθηκε δεύτερη οθόνη)
            w, h, x, y = map(int, m.groups())
            w, h = min(w, self.winfo_screenwidth()), min(h, self.winfo_screenheight())
            x, y = max(0, min(x, self.winfo_screenwidth() - 200)), max(0, min(y, self.winfo_screenheight() - 200))
            geometry = f"{w}x{h}+{x}+{y}"
        self.geometry(geometry)
        if win.get("zoomed", True):
            self.state("zoomed")

    def on_close(self, restart=False):
        """Κλείσιμο: κρατά μέγεθος, θέση και πλάτη πλαισίων για την επόμενη φορά."""
        zoomed = self.state() == "zoomed"
        # Μεγιστοποιημένο: κρατάμε το προηγούμενο «κανονικό» μέγεθος (αν δεν υπάρχει, ένα λογικό), όχι κενό
        normal = self.cfg.get("window", {}).get("geometry") or "1320x720+40+40"
        self.cfg["window"] = {"zoomed": zoomed, "geometry": normal if zoomed else self.geometry()}
        if not restart:
            self._remember_width("side", self.side)
            for key in list(SECTIONS) + ["chat"]:
                if key not in self.detached:
                    self._remember_width(key, self.detachables[key])
        save_config(self.cfg)
        self.destroy()
        if restart:
            import subprocess
            frozen = getattr(sys, "frozen", False)  # στο .exe: ξανανοίγει το ίδιο το .exe
            subprocess.Popen([sys.executable] + (sys.argv[1:] if frozen else [os.path.abspath(sys.argv[0])] + sys.argv[1:]))

    def about(self):
        """Η τρέχουσα έκδοση και το ιστορικό αλλαγών (από το CHANGELOG.md)."""
        win = tk.Toplevel(self, bg=BG, padx=14, pady=12)
        win.title("Σχετικά με το XrysaStudy")
        win.transient(self)
        tk.Label(win, text=f"  XrysaStudy — έκδοση {VERSION}", image=self.icon("📚", 32) or "", compound="left",
                 bg=BG, fg=TEXT, font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(win, text="Βοηθός για διάβασμα, ασκήσεις και εργασίες πανεπιστημίου.", bg=BG, fg=MUTED,
                 font=FONT).pack(anchor="w", pady=(2, 8))
        box = tk.Text(win, bg=PANEL, fg=TEXT, relief="flat", wrap="word", width=80, height=24, padx=12, pady=8,
                      highlightthickness=1, highlightbackground=BORDER, font=("Segoe UI", 10))
        box.tag_config("#", font=("Segoe UI", 14, "bold"), spacing3=6)
        box.tag_config("##", font=("Segoe UI", 11, "bold"), foreground=ACCENT, spacing1=10, spacing3=2)
        box.tag_config("-", lmargin1=10, lmargin2=24)
        for line in read_changelog().splitlines():
            kind, txt = line_kind(line.strip())
            box.insert("end", ("•  " if kind == "-" else "") + "".join(p for p, _ in inline_parts(txt)) + "\n", kind)
        box.config(state="disabled")
        box.pack(fill="both", expand=True)
        self._button(win, "Κλείσιμο", win.destroy, icon="❌").pack(fill="x", pady=(8, 0))

    def check_updates(self, manual=False):
        """Ρωτά το GitHub αν υπάρχει νεότερη έκδοση· στο αυτόματο (στο άνοιγμα) μιλά μόνο αν υπάρχει."""
        if not GITHUB_REPO:
            if manual:
                messagebox.showinfo("Αναβάθμιση", "Το πρόγραμμα δεν έχει συνδεθεί ακόμα με το GitHub.\n"
                                                  f"Έχεις την έκδοση {VERSION}.")
            return

        def work():
            try:
                self.q.put(("update", "info", (manual, latest_release(GITHUB_REPO))))
            except Exception as e:
                self.q.put(("update", "info", (manual, e)))
        threading.Thread(target=work, daemon=True).start()

    def _update_result(self, manual, result):
        if isinstance(result, Exception):
            if manual:
                messagebox.showwarning("Αναβάθμιση", f"Δεν έγινε ο έλεγχος — έλεγξε τη σύνδεση στο internet.\n({result})")
            return
        latest, url, setup = result
        if version_tuple(latest) <= version_tuple(VERSION):
            if manual:
                messagebox.showinfo("Αναβάθμιση", f"Έχεις την τελευταία έκδοση ({VERSION}).")
            return
        installed = getattr(sys, "frozen", False)  # τρέχει το εγκατεστημένο .exe (και όχι ο κώδικας με python)
        if not (installed and setup):
            if messagebox.askyesno("Νέα έκδοση", f"Υπάρχει νέα έκδοση {latest} (έχεις την {VERSION}).\n"
                                                 "Θέλεις να ανοίξει η σελίδα για να την κατεβάσεις;"):
                import webbrowser
                webbrowser.open(url)
            return
        if messagebox.askyesno("Νέα έκδοση", f"Υπάρχει νέα έκδοση {latest} (έχεις την {VERSION}).\n"
                                             "Να κατέβει και να εγκατασταθεί τώρα;\n"
                                             "Το πρόγραμμα θα κλείσει και θα ξανανοίξει μόνο του."):
            self.set_status(f"Κατεβάζω την έκδοση {latest}…", ACCENT)
            threading.Thread(target=self._download_setup, args=(setup, latest), daemon=True).start()

    def _download_setup(self, url, latest):
        """Κατεβάζει το νέο Setup.exe στο παρασκήνιο· μετά το τρέχει και κλείνει το πρόγραμμα."""
        path = os.path.join(tempfile.gettempdir(), f"XrysaStudy-Setup-{latest}.exe")
        try:
            data = http_get(url)
            with open(path, "wb") as f:
                f.write(data)
        except Exception as e:
            self.q.put(("status", "info", f"Δεν κατέβηκε η νέα έκδοση: {e}"))
            return
        self.after(0, lambda: self._run_setup(path))

    def _run_setup(self, path):
        import subprocess
        # /SILENT: εγκατάσταση χωρίς ερωτήσεις, μόνο με μπάρα προόδου· στο τέλος ξανανοίγει το XrysaStudy
        subprocess.Popen([path, "/SILENT", "/SP-", "/CLOSEAPPLICATIONS", "/NORESTART"])
        self.on_close()

    def api_key(self, provider):
        key = self.cfg["keys"].get(provider) or os.environ.get(KEY_ENV[provider], "")
        if not key:
            messagebox.showinfo("Κλειδί API", f"Βάλε πρώτα το κλειδί του {provider} από τις «Ρυθμίσεις».")
        return key

    # ---------- sections και αρχεία ----------
    # ---------- πλαίσια: άνοιγμα, κλείσιμο, ξεχωριστό παράθυρο ----------
    def pane_width(self, key, default):
        """Το πλάτος που είχε το πλαίσιο την τελευταία φορά (σε pixels), αλλιώς το default (π.χ. "9.5c")."""
        return self.cfg.get("panes", {}).get(key) or self.winfo_pixels(default)

    def _remember_width(self, key, widget):
        if widget.winfo_ismapped() and widget.winfo_width() > 50:
            self.cfg.setdefault("panes", {})[key] = widget.winfo_width()

    def _place(self, key):
        """Βάζει ένα πλαίσιο στη θέση του μέσα στο πρόγραμμα (αν δεν είναι σε ξεχωριστό παράθυρο)."""
        if key in self.detached:
            self.tk.call("wm", "deiconify", self.detachables[key]._w)
            self.tk.call("raise", self.detachables[key]._w)
            return
        w = self.detachables[key]
        if key == "result":
            self.right.add(w, stretch="always", minsize=self.winfo_pixels("5c"))
            return
        chat_docked = self.chat_open and "chat" not in self.detached
        before = self.detachables["chat"] if key != "chat" and chat_docked else self.right
        self.body.add(w, before=before, width=self.pane_width(key, "6.5c" if key == "chat" else "8.5c"),
                      minsize=self.winfo_pixels("5c"), stretch="never")

    def _hide(self, key):
        """Βγάζει ένα πλαίσιο από την οθόνη (μέσα στο πρόγραμμα ή σε ξεχωριστό παράθυρο)."""
        w = self.detachables[key]
        if key in self.detached:
            self.tk.call("wm", "forget", w._w)
            self.detached.discard(key)
            self._detach_label(key)
        elif str(w) in map(str, self.body.panes()):
            self._remember_width(key, w)
            self.body.forget(w)

    def toggle_detach(self, key):
        """«Παράθυρο»: το πλαίσιο γίνεται κανονικό παράθυρο των Windows. «Επιστροφή»: ξαναμπαίνει στη θέση του."""
        w = self.detachables[key]
        if key in self.detached:
            self.tk.call("wm", "forget", w._w)
            self.detached.discard(key)
            self._place(key)
        else:
            x, y, width, height = w.winfo_rootx(), w.winfo_rooty(), w.winfo_width(), w.winfo_height()
            (self.right if key == "result" else self.body).forget(w)
            self.tk.call("wm", "manage", w._w)
            title = {"result": "Αποτέλεσμα", "chat": "Chat"}.get(key) or SECTIONS[key]
            self.tk.call("wm", "title", w._w, f"XrysaStudy — {title}")
            self.tk.call("wm", "geometry", w._w, f"{max(width, 300)}x{max(height, 300)}+{x + 30}+{y + 30}")
            self.tk.call("wm", "protocol", w._w, "WM_DELETE_WINDOW", self.register(lambda: self.toggle_detach(key)))
            self.tk.call("wm", "deiconify", w._w)  # χωρίς αυτό το νέο παράθυρο μένει κρυμμένο
            self.detached.add(key)
        self._detach_label(key)

    def toggle_chat(self):
        if self.chat_open:
            self._hide("chat")
            self.chat_open = False
            self.chat_btn.config(bg=PANEL)
        else:
            self.chat_open = True
            self._place("chat")
            self.chat_btn.config(bg="#dbe9fb")
            self.chat_entry.focus_set()

    def toggle_section(self, key):
        """Ανοίγει το πλαίσιο του section (κλείνοντας όποιο άλλο ήταν ανοιχτό)· ξανά πάτημα το κλείνει."""
        if self.section:
            self._hide(self.section)
            self.section_btns[self.section].config(bg=PANEL, fg=TEXT)
        if self.section == key:
            self.section = None
            return
        self.section = key
        self._place(key)
        self.section_btns[key].config(bg=ACCENT, fg="white")
        n = len(self.files[key])
        self.set_status(f"{SECTIONS[key]}: {n} αρχεία φορτωμένα." if n else f"{SECTIONS[key]}: φόρτωσε αρχεία και πες μου τι θέλεις.")

    def add_files(self, key):
        for p in filedialog.askopenfilenames(title="Διάλεξε αρχεία", filetypes=FILE_TYPES,
                                             initialdir=self.folders["data"]):
            self._add_file(key, p)

    def _add_file(self, key, path):
        if path not in self.files[key]:
            self.files[key].append(path)
            self.lists[key].insert("end", os.path.basename(path))
            self._save_files()

    def remove_files(self, key):
        for i in reversed(self.lists[key].curselection()):
            self.lists[key].delete(i)
            del self.files[key][i]
        self._save_files()

    def _save_files(self):
        # Τα αρχεία και το «Μόνο από αυτά» κάθε section μένουν και την επόμενη φορά
        self.cfg["files"] = self.files
        self.cfg["only"] = {k: v.get() for k, v in self.only.items()}
        self.cfg["official"] = self.official.get()
        self.cfg["autoproof"] = self.autoproof.get()
        save_config(self.cfg)

    def _official_changed(self):
        """Με τικ στις «επίσημες πηγές», η «Μορφή παραπομπών» φωτίζεται για να μην ξεχαστεί."""
        self._save_files()
        self.cite_label.config(bg="#fff3a3" if self.official.get() else BG)

    def choose_citation(self):
        style = self.cite_style.get()
        if style == CUSTOM_STYLE and not self.citation_example():
            self.cite_style.set(self.cfg["citation_style"])  # ακύρωση: μένει η προηγούμενη μορφή
            return
        self.cfg["citation_style"] = style
        save_config(self.cfg)
        self.set_status(f"Μορφή παραπομπών: {style}", "green")

    def citation_example(self):
        """Παράθυρο για δικό σου παράδειγμα παραπομπής. Επιστρέφει True αν αποθηκεύτηκε."""
        win = tk.Toplevel(self, bg=BG, padx=14, pady=12)
        win.title("Δικό μου παράδειγμα παραπομπής")
        win.transient(self)
        win.grab_set()
        tk.Label(win, text="Επικόλλησε ένα παράδειγμα, π.χ. από τις οδηγίες του καθηγητή σου, μέσα στο κείμενο\n"
                           "και στη βιβλιογραφία. Το Claude θα ακολουθεί ακριβώς αυτή τη μορφή.",
                 bg=BG, fg=TEXT, font=BOLD, justify="left").pack(anchor="w")
        box = self._textbox(win, height=8, width=80)
        box.insert("1.0", self.cfg["citation_example"] or
                   "Μέσα στο κείμενο: (Παπαδόπουλος, 2020, σ. 15)\n"
                   "Στη βιβλιογραφία: Παπαδόπουλος, Γ. (2020). Τίτλος βιβλίου. Αθήνα: Εκδότης.")
        box.pack(fill="both", expand=True, pady=8)
        saved = []

        def save():
            text = box.get("1.0", "end").strip()
            if text:
                self.cfg["citation_example"] = text
                saved.append(True)
            win.destroy()
        row = tk.Frame(win, bg=BG)
        row.pack(fill="x")
        self._button(row, "Αποθήκευση", save, big=True, icon="💾").pack(side="left", expand=True, fill="x", padx=(0, 3))
        self._button(row, "Άκυρο", win.destroy, big=True, icon="❌").pack(side="left", expand=True, fill="x", padx=(3, 0))
        self.wait_window(win)
        return bool(saved)

    def load_statement(self):
        path = filedialog.askopenfilename(title="Διάλεξε εκφώνηση", filetypes=FILE_TYPES,
                                          initialdir=self.folders["data"])
        if not path:
            return
        ext = os.path.splitext(path)[1].lower()
        if ext == ".pdf" or ext in IMAGE_TYPES:
            # PDF και εικόνες δεν μετατρέπονται σε κείμενο εδώ· στέλνονται ολόκληρα μαζί με τα αρχεία
            self._add_file("exercise", path)
            self.set_status("Η εκφώνηση μπήκε στη λίστα αρχείων.")
            return
        try:
            block = file_block(path)
        except Exception as e:
            messagebox.showerror("Εκφώνηση", f"Δεν διαβάστηκε το αρχείο:\n{e}")
            return
        self.boxes["exercise"].delete("1.0", "end")
        self.boxes["exercise"].insert("1.0", block["text"].split("\n", 1)[1])

    def _blocks(self, paths):
        """Διαβάζει αρχεία· σε σφάλμα δείχνει μήνυμα και επιστρέφει None."""
        try:
            return [file_block(p) for p in paths]
        except Exception as e:
            messagebox.showerror("Αρχείο", f"Δεν διαβάστηκε κάποιο αρχείο:\n{e}")
            return None

    def system_for(self, base, key):
        """Προσθέτει στις οδηγίες τις μόνιμες οδηγίες και το «Μόνο από αυτά τα αρχεία». None = ακύρωση."""
        strict = bool(key) and self.only[key].get()
        if strict and not self.files[key]:
            messagebox.showinfo("Αρχεία", "Τσέκαρες «Απάντα μόνο από αυτά τα αρχεία», αλλά δεν έχεις φορτώσει αρχεία.\n"
                                          "Φόρτωσε αρχεία ή βγάλε το τικ.")
            return None
        parts = [base, GREEK_RULE]
        if self.cfg["instructions"].strip():
            parts.append("Μόνιμες οδηγίες της φοιτήτριας (ακολούθησέ τες πάντα):\n" + self.cfg["instructions"].strip())
        if strict:
            parts.append(STRICT_NOTE)
        return "\n\n".join(parts)

    # ---------- εργασίες των sections ----------
    def build_task(self, key):
        """Ετοιμάζει (οδηγίες, περιεχόμενο, όνομα αρχείου) για το section· None αν λείπει κάτι."""
        text = self.boxes[key].get("1.0", "end").strip()
        files = self._blocks(self.files[key])
        if files is None:
            return None
        if key == "study":
            if not files:
                messagebox.showinfo("Βοήθημα", "Φόρτωσε πρώτα τα αρχεία για το βοήθημα (π.χ. το PDF του μαθήματος).")
                return None
            content = files + [{"type": "text", "text": ("=== ΤΙ ΖΗΤΑΕΙ Η ΦΟΙΤΗΤΡΙΑ ===\n" + text) if text else "Φτιάξε το βοήθημα."}]
            name = os.path.splitext(os.path.basename(self.files[key][0]))[0] + " - βοήθημα"
            return STUDY_PROMPT.format(level=STUDY_LEVELS[self.level.get()]), content, name
        if key == "exercise":
            if not text and not files:
                messagebox.showinfo("Άσκηση", "Γράψε ή φόρτωσε πρώτα την εκφώνηση.")
                return None
            content = ([{"type": "text", "text": "=== ΑΡΧΕΙΑ (σημειώσεις και δεδομένα) ==="}] + files if files else [])
            content.append({"type": "text", "text": "=== ΕΚΦΩΝΗΣΗ ===\n" + (text or "(βλ. συνημμένα αρχεία)")})
            return EXERCISE_PROMPT, content, "Λύση άσκησης"
        if not text:
            messagebox.showinfo("Εργασία", "Γράψε πρώτα το θέμα και τις οδηγίες της εργασίας.")
            return None
        content = ([{"type": "text", "text": "=== ΠΗΓΕΣ ==="}] + files if files else [])
        content.append({"type": "text", "text": "=== ΘΕΜΑ ΚΑΙ ΟΔΗΓΙΕΣ ===\n" + text})
        return ESSAY_PROMPT + "\n\n" + citation_rule(self.cfg), content, "Εργασία"

    def opinion(self, provider):
        if not self.section:
            messagebox.showinfo("Δεύτερη γνώμη", "Άνοιξε πρώτα «Βοήθημα», «Άσκηση» ή «Εργασία».")
            return
        self.run_section(provider, self.section)

    def run_section(self, provider, key):
        task = self.build_task(key)
        if not task:
            return
        system, content, name = task
        system = self.system_for(system, key)
        if system is None:
            return
        if provider == "Claude":
            chosen = [n for n, v in self.include.items() if v.get()]
            missing = [n for n in chosen if not self.out[n]]
            if missing:
                messagebox.showinfo("Δεύτερη γνώμη", f"Δεν υπάρχει ακόμα γνώμη από {', '.join(missing)}.\n"
                                                     f"Πάτα πρώτα «{missing[0]} ▶» ή βγάλε το τικ.")
                return
            if chosen:
                content = content + [{"type": "text", "text": f"=== ΑΠΑΝΤΗΣΗ {n} ===\n{self.out[n]}"} for n in chosen] \
                    + [{"type": "text", "text": MERGE_NOTE}]
        prepare = None
        self.sources.pop(provider, None)  # νέο αποτέλεσμα: τα άρθρα (αν υπάρχουν) ξαναβρίσκονται
        if key == "essay" and self.official.get():
            topic = self.boxes["essay"].get("1.0", "end").strip()
            prepare = lambda *args: self._add_sources(topic, *args)
        self.show_tab(provider)
        if self.ask(provider, provider, system, [{"role": "user", "content": content}],
                    f"Το {provider} δουλεύει… (μπορεί να πάρει 1–2 λεπτά)", prepare):
            self.names[provider] = name
            self.backup.pop(provider, None)
            self.jobs[provider] = "doc"
            self.kinds[provider] = key

    def _add_sources(self, topic, provider, key, model, system, messages, usage=None):
        """Τρέχει στο παρασκήνιο πριν γραφτεί η εργασία: βρίσκει άρθρα και τα προσθέτει στο υλικό."""
        self.q.put(("status", "info", "Ετοιμάζω όρους αναζήτησης στα αγγλικά…"))
        reply = "".join(stream_reply(provider, key, model, QUERY_PROMPT,
                                     [{"role": "user", "content": [{"type": "text", "text": topic}]}], usage))
        queries = [line.strip(" -•\"'0123456789.") for line in reply.splitlines() if line.strip()][:2]
        self.q.put(("status", "info", f"Ψάχνω άρθρα στο PubMed και στο OpenAlex: {' / '.join(queries)}…"))
        try:
            sources = find_sources(queries)
        except OSError as e:
            raise SourceError(f"Δεν έγινε η αναζήτηση πηγών — έλεγξε τη σύνδεση στο internet ({e}).")
        if not sources:
            raise SourceError("Δεν βρέθηκαν επιστημονικά άρθρα για αυτό το θέμα. Δοκίμασε πιο γενική διατύπωση "
                              "ή βγάλε το τικ «Από επίσημες πηγές».")
        self.q.put(("status", "info", f"Βρέθηκαν {len(sources)} άρθρα. Γράφω την εργασία στα ελληνικά…"))
        listed = "=== ΕΠΙΣΤΗΜΟΝΙΚΑ ΑΡΘΡΑ ===\n" + format_sources(sources)
        self.sources[provider] = listed  # κρατιούνται για μετέπειτα «✏ Αλλαγές» με σωστές παραπομπές
        content = [{"type": "text", "text": listed}] + messages[0]["content"]
        return system + "\n\n" + CITATION_NOTE, [{"role": "user", "content": content}]

    def toggle_manual(self):
        """1ο πάτημα: το λευκό πεδίο γίνεται επεξεργάσιμο. 2ο πάτημα: αποθηκεύονται οι αλλαγές."""
        if self.editing:
            self._finish_manual()
            return
        tab = self.tab
        if not self.out[tab] or tab in self.busy:
            messagebox.showinfo("Επεξεργασία", "Δεν υπάρχει ακόμα έτοιμο κείμενο εδώ, ή κάτι δουλεύει ακόμα.")
            return
        self.editing = tab
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", self.out[tab])  # με τα σημάδια μορφής, ώστε να μένουν τίτλοι και έντονα
        self.text.edit_reset()
        self.text.focus_set()
        self.manual_btn.config(text=" Τέλος επεξεργασίας", image=self.icon("💾", 16) or "", bg="#fff3a3")
        self.set_status("Γράψε ή σβήσε απευθείας στο κείμενο. Σημάδια: «# » τίτλος, «## » υπότιτλος, «- » κουκκίδα, "
                        "**έντονα**. Πάτα «Τέλος επεξεργασίας» όταν τελειώσεις.", ACCENT)

    def _finish_manual(self):
        """Αποθηκεύει τη χειροκίνητη επεξεργασία (αν υπάρχει) και ξαναδείχνει το κείμενο μορφοποιημένο."""
        tab, self.editing = self.editing, None
        if not tab:
            return
        new = self.text.get("1.0", "end-1c").strip()
        changed = new != self.out[tab].strip()
        if changed:
            self.backup[tab] = self.out[tab]
            self.out[tab] = new
        self.manual_btn.config(text=" Επεξεργασία", image=self.icon("✏️", 16) or "", bg=PANEL)
        self.render()
        self.set_status("Οι αλλαγές σου αποθηκεύτηκαν. Το «Αρχικό» τις αναιρεί." if changed else "Δεν άλλαξε τίποτα.",
                        "green" if changed else MUTED)

    def request_edit(self):
        """Στέλνει στο Claude το έτοιμο κείμενο και τις αλλαγές· πίσω έρχονται μόνο οι αλλαγές."""
        self._finish_manual()
        change = self.edit_entry.get().strip()
        tab = self.tab
        if not change:
            return
        if not self.out[tab] or tab in self.busy or "edit" in self.busy:
            messagebox.showinfo("Αλλαγές", "Δεν υπάρχει ακόμα έτοιμο κείμενο εδώ, ή κάτι άλλο δουλεύει ακόμα.")
            return
        prompt = EDIT_PROMPT + ("\n\n" + citation_rule(self.cfg) if self.kinds.get(tab) == "essay" else "")
        system = self.system_for(prompt, self.section)
        files = self._blocks(self.files[self.section] if self.section else [])
        if system is None or files is None:
            return
        content = files + ([{"type": "text", "text": self.sources[tab]}] if tab in self.sources else []) + [
            {"type": "text", "text": "=== ΚΕΙΜΕΝΟ ===\n" + self.out[tab]},
            {"type": "text", "text": "=== ΑΛΛΑΓΕΣ ΠΟΥ ΖΗΤΑΩ ===\n" + change}]
        if self.ask("edit", "Claude", system, [{"role": "user", "content": content}], "Ετοιμάζω τις αλλαγές…"):
            self.edit_tab = tab
            self.edit_entry.delete(0, "end")

    def _apply_edit(self):
        tab = self.edit_tab
        edits = parse_edits(self.edit_reply)
        if not edits:  # το Claude απάντησε με κείμενο αντί για αλλαγές: δείχνουμε τι είπε, για να φαίνεται το γιατί
            self.set_status("Το Claude δεν έστειλε αλλαγές — δες την απάντησή του.", "red")
            self.show_report("Αλλαγές", "# Το Claude δεν έκανε αλλαγές\n## Η απάντησή του\n"
                             + self.edit_reply.strip()[:3000])
            return
        new, applied, failed = apply_edits(self.out[tab], edits)
        if not applied:
            self.set_status("Δεν έγινε καμία αλλαγή — δοκίμασε να το διατυπώσεις αλλιώς.", "red")
            return
        self.backup[tab] = self.out[tab]
        self.out[tab] = new
        if tab == self.tab:
            self.render()
            self._highlight(applied)
        msg = f"Έγιναν {len(applied)} αλλαγές (με κίτρινο). Το «↩ Αρχικό» τις αναιρεί."
        if failed:
            msg += f" {failed} αλλαγές παραλείφθηκαν γιατί δεν βρέθηκε το σημείο τους."
        self.set_status(msg, "green")
        if self.autoproof.get():
            self._rewrite(PROOF_PROMPT, "Κάνω αυτόματο ορθογραφικό έλεγχο στις αλλαγές…", tab, keep_backup=True)

    def _highlight(self, snippets):
        """Βάφει κίτρινα στο λευκό πεδίο τα κομμάτια που άλλαξαν."""
        for snippet in snippets:
            for line in snippet.splitlines():
                plain = "".join(part for part, _ in inline_parts(line_kind(line.strip())[1])).strip()
                idx = self.text.search(plain, "1.0", "end") if len(plain) > 3 else ""
                if idx:
                    self.text.tag_add("changed", idx, f"{idx}+{len(plain)}c")

    def check_originality(self):
        """Σύγκριση με τις πηγές: αυτούσια αντιγραφή τοπικά (κόκκινο), κοντινή απόδοση με το Claude (πορτοκαλί)."""
        self._finish_manual()
        tab = self.tab
        if not self.out[tab] or tab in self.busy or "orig" in self.busy:
            messagebox.showinfo("Πρωτοτυπία", "Δεν υπάρχει ακόμα έτοιμο κείμενο εδώ, ή κάτι δουλεύει ακόμα.")
            return
        section = self.kinds.get(tab)
        try:
            sources = {os.path.basename(p): source_text(p) for p in (self.files[section] if section else [])}
        except Exception as e:
            messagebox.showerror("Πρωτοτυπία", f"Δεν διαβάστηκε κάποια πηγή:\n{e}")
            return
        if tab in self.sources:
            sources["Άρθρα PubMed/OpenAlex"] = self.sources[tab]
        sources = {name: text for name, text in sources.items() if text.strip()}
        if not sources:
            messagebox.showinfo("Πρωτοτυπία", "Δεν υπάρχουν πηγές για σύγκριση.\nΦόρτωσε αρχεία στο πλαίσιο ή φτιάξε "
                                              "την εργασία «Από επίσημες πηγές».")
            return
        self.render()  # καθαρό κείμενο, χωρίς χρώματα από προηγούμενο έλεγχο
        shown = strip_references(self.text.get("1.0", "end-1c"))
        spans, pct = find_copied(shown, sources)
        for start, end, _ in spans:  # αναζήτηση και όχι θέση: οι εικόνες των σχεδιαγραμμάτων μετρούν ως χαρακτήρες
            idx = self.text.search(shown[start:end], "1.0", "end")
            if idx:
                self.text.tag_add("copied", idx, f"{idx}+{end - start}c")
        self.orig_ctx = {"tab": tab, "pct": pct, "copied": [(shown[s:e], name) for s, e, name in spans]}
        # shortcut: κάθε πηγή κόβεται στους 60.000 χαρακτήρες για να μένει λογικό το κόστος· αν χρειαστεί, συγκρίνουμε τμηματικά
        content = [{"type": "text", "text": f"=== ΠΗΓΗ: {name} ===\n{text[:60000]}"} for name, text in sources.items()]
        content.append({"type": "text", "text": "=== ΕΡΓΑΣΙΑ ===\n" + shown})
        if not self.ask("orig", "Claude", ORIG_PROMPT, [{"role": "user", "content": content}],
                        f"Αυτούσια ίδιο με πηγή: {pct}%. Ελέγχω και για κοντινή απόδοση ή μετάφραση…"):
            self._show_originality(None)  # χωρίς κλειδί: μόνο ο τοπικός έλεγχος

    def _show_originality(self, close):
        """Πορτοκαλί στα κοντινά κομμάτια και παράθυρο με την αναφορά. close=None: δεν έγινε ο έλεγχος του Claude."""
        ctx, self.orig_ctx = self.orig_ctx, None
        if not ctx:
            return
        found = []
        for passage, why in close or []:
            idx = self.text.search(passage.strip(), "1.0", "end") if ctx["tab"] == self.tab and passage.strip() else ""
            if idx:
                self.text.tag_add("close", idx, f"{idx}+{len(passage.strip())}c")
            found.append((passage.strip(), why.strip()))

        lines = [f"# Έλεγχος πρωτοτυπίας ({ctx['tab']})",
                 f"## Αυτούσια ίδιο με πηγή: {ctx['pct']}% του κειμένου (κόκκινο)"]
        lines += [f"- «{text[:200]}» — πηγή: {name}" for text, name in ctx["copied"]] or ["- Τίποτα. 👍"]
        if close is None:
            lines.append("## Κοντινή απόδοση ή μετάφραση: δεν ελέγχθηκε (χρειάζεται το Claude)")
        else:
            lines.append(f"## Κοντινή απόδοση ή μετάφραση: {len(found)} σημεία (πορτοκαλί)")
            lines += [f"- «{text[:200]}» — {why}" for text, why in found] or ["- Τίποτα. 👍"]
        if ctx["copied"] or found:
            lines += ["## Τι να κάνεις",
                      "- Γράψε τα σημειωμένα κομμάτια με δικά σου λόγια (π.χ. στο «Αλλαγές»: «ξαναγράψε με δικά μου λόγια "
                      "την πρόταση που ξεκινά …»), ή",
                      "- βάλε τα σε «εισαγωγικά» με παραπομπή στην πηγή."]
        lines += ["## Να ξέρεις",
                  "- Η σύγκριση γίνεται μόνο με τις πηγές που χρησιμοποιήθηκαν (αρχεία και άρθρα), όχι με όλο το internet "
                  "ή με τη βάση του Turnitin. Η Βιβλιογραφία δεν ελέγχεται."]
        self.show_report("Έλεγχος πρωτοτυπίας", "\n".join(lines))
        self.set_status(f"Πρωτοτυπία: {ctx['pct']}% αυτούσια ίδιο"
                        + ("" if close is None else f", {len(found)} σημεία κοντινής απόδοσης") + ".",
                        "green" if not (ctx["copied"] or found) else "#b45309")

    def show_report(self, title, md):
        """Απλό παράθυρο που δείχνει μια αναφορά με τίτλους και κουκκίδες."""
        win = tk.Toplevel(self, bg=BG, padx=14, pady=12)
        win.title(title)
        win.transient(self)
        box = tk.Text(win, bg=PANEL, fg=TEXT, relief="flat", wrap="word", width=90, height=24, padx=12, pady=8,
                      highlightthickness=1, highlightbackground=BORDER, font=("Segoe UI", 10))
        box.tag_config("#", font=("Segoe UI", 14, "bold"), spacing3=6)
        box.tag_config("##", font=("Segoe UI", 11, "bold"), foreground=ACCENT, spacing1=10, spacing3=2)
        box.tag_config("-", lmargin1=10, lmargin2=24)
        for line in md.splitlines():
            kind, txt = line_kind(line.strip())
            box.insert("end", ("•  " if kind == "-" else "") + plain_line(txt) + "\n", kind)
        box.config(state="disabled")
        box.pack(fill="both", expand=True)
        self._button(win, "Κλείσιμο", win.destroy, icon="❌").pack(fill="x", pady=(8, 0))
        return win

    def humanize(self):
        self._rewrite(HUMANIZE_PROMPT, "Ξαναγράφω το κείμενο σε πιο ανθρώπινο ύφος…")

    def proofread(self):
        self._rewrite(PROOF_PROMPT, "Κάνω ορθογραφικό και συντακτικό έλεγχο…")

    def _rewrite(self, prompt, status, tab=None, keep_backup=False):
        """Το Claude ξαναγράφει το κείμενο μιας καρτέλας· το «↩ Αρχικό» φέρνει πίσω την προηγούμενη μορφή.
        keep_backup: ο αυτόματος έλεγχος μετά από αλλαγές κρατά ως «Αρχικό» το κείμενο πριν τις αλλαγές."""
        self._finish_manual()
        tab = tab or self.tab
        if not self.out[tab] or tab in self.busy or "edit" in self.busy:
            messagebox.showinfo("Επεξεργασία", "Δεν υπάρχει ακόμα έτοιμο κείμενο σε αυτή την καρτέλα.")
            return
        old = self.out[tab]
        if self.ask(tab, "Claude", prompt, [{"role": "user", "content": old}], status):
            if keep_backup:
                self.backup.setdefault(tab, old)
            else:
                self.backup[tab] = old
            self.jobs[tab] = "rewrite"

    def undo_humanize(self):
        self._finish_manual()
        if self.tab in self.backup and self.tab not in self.busy:
            self.out[self.tab] = self.backup.pop(self.tab)
            self.render()
            self.set_status("Επανήλθε το αρχικό κείμενο.")

    # ---------- chat ----------
    def send_chat(self):
        question = self.chat_entry.get().strip()
        if not question or "chat" in self.busy:
            return
        system = self.system_for(CHAT_PROMPT, self.section)
        if system is None:
            return
        # Το υλικό του ανοιχτού section μπαίνει στην αρχή της συζήτησης, ώστε το Claude να το «βλέπει» σε κάθε ερώτηση
        context = self._blocks(self.files[self.section] if self.section else [])
        if context is None:
            return
        if self.out["Claude"]:
            context.append({"type": "text", "text": "--- Αυτό που φαίνεται τώρα στην οθόνη ---\n" + self.out["Claude"]})
        if context:
            context[-1]["cache_control"] = {"type": "ephemeral"}  # φθηνότερες επόμενες ερωτήσεις
        history = self.chat_history + [{"role": "user", "content": question}]
        messages = [dict(m) for m in history]
        messages[0]["content"] = context + [{"type": "text", "text": history[0]["content"]}]
        if not self.ask("chat", "Claude", system, messages, "Το Claude σκέφτεται…"):
            return
        self.chat_history = history
        self.chat_entry.delete(0, "end")
        self._chat_write("Εσύ: ", "me")
        self._chat_write(question + "\n")
        self._chat_write("Claude: ", "bot")

    def _chat_write(self, text, tag=None):
        self.chat_view.config(state="normal")
        self.chat_view.insert("end", text, tag)
        self.chat_view.see("end")
        self.chat_view.config(state="disabled")

    # ---------- κλήσεις στο παρασκήνιο ----------
    def ask(self, target, provider, system, messages, status, prepare=None):
        """Ξεκινά μια κλήση· target = καρτέλα ή 'chat'. prepare: προετοιμασία στο παρασκήνιο. True αν ξεκίνησε."""
        if target in self.busy:
            self.set_status("Περίμενε να τελειώσει η προηγούμενη εργασία εδώ.", "red")
            return False
        key = self.api_key(provider)
        if not key:
            return False
        self.busy.add(target)
        if target == "chat":
            self.chat_reply = ""
        elif target == "edit":
            self.edit_reply = ""
        elif target == "orig":
            self.orig_reply = ""
        else:
            self.out[target] = ""
            if target == self.tab:
                self.render()
        self.set_status(status, ACCENT)
        args = (target, provider, key, self.cfg["models"][provider], system, messages, prepare)
        threading.Thread(target=self._work, args=args, daemon=True).start()
        return True

    def _work(self, target, provider, key, model, system, messages, prepare=None):
        # Τρέχει στο παρασκήνιο για να μην «παγώνει» το παράθυρο
        usage = {}
        try:
            if prepare:
                system, messages = prepare(provider, key, model, system, messages, usage)
            for chunk in stream_reply(provider, key, model, system, messages, usage):
                self.q.put((target, "text", chunk))
            self.q.put((target, "done", None))
        except Exception as e:
            self.q.put((target, "error", friendly_error(provider, e)))
        finally:
            if usage:  # χρεώνεται ό,τι στάλθηκε, ακόμα κι αν η κλήση δεν ολοκληρώθηκε
                self.q.put(("cost", "info", (cost_of(provider, usage), sum(usage.values()))))

    def _poll(self):
        try:
            while True:
                target, kind, val = self.q.get_nowait()
                if target == "status":  # μήνυμα προόδου από το παρασκήνιο
                    self.set_status(val, ACCENT)
                    continue
                if target == "update":  # απάντηση του GitHub για νέα έκδοση
                    self._update_result(*val)
                    continue
                if target == "cost":  # κόστος μιας κλήσης που μόλις τελείωσε
                    add_cost(self.cfg["costs"], val[0], datetime.date.today(), val[1])
                    save_config(self.cfg)
                    self.show_cost()
                    continue
                if kind == "text":
                    if target == "chat":
                        self.chat_reply += val
                        self._chat_write(val)
                    elif target == "edit":  # οι αλλαγές δεν εμφανίζονται όσο γράφονται· εφαρμόζονται στο τέλος
                        self.edit_reply += val
                    elif target == "orig":
                        self.orig_reply += val
                    else:
                        self.out[target] += val
                        if target == self.tab:
                            self._view_insert(val)
                    continue
                self.busy.discard(target)
                if kind == "done":
                    if target == "chat":
                        self.chat_history.append({"role": "assistant", "content": self.chat_reply})
                        self._chat_write("\n")
                        self.set_status("Έτοιμο.", "green")
                    elif target == "edit":
                        self._apply_edit()
                    elif target == "orig":
                        self._show_originality(ORIG_BLOCK.findall(self.orig_reply))
                    else:
                        if target == self.tab:
                            self.render()
                        self.set_status(f"Έτοιμο ({target})! Μπορείς να κάνεις «Εξαγωγή» ή «Εκτύπωση».", "green")
                        if self.jobs.pop(target, None) == "doc" and self.autoproof.get():
                            self._rewrite(PROOF_PROMPT, f"Κάνω αυτόματο ορθογραφικό έλεγχο ({target})…", target)
                else:
                    self.jobs.pop(target, None)
                    if target == "chat":
                        self.chat_history.pop()  # η ερώτηση δεν απαντήθηκε· δεν μένει στο ιστορικό
                        self._chat_write("(σφάλμα)\n")
                    elif target in self.backup:  # απέτυχε το «Πιο ανθρώπινο»: γυρνάμε στο αρχικό
                        self.out[target] = self.backup.pop(target)
                        if target == self.tab:
                            self.render()
                    self.set_status(f"Κάτι πήγε στραβά — {val}", "red")
                    if target == "orig":  # ο τοπικός έλεγχος έγινε· δείχνουμε τουλάχιστον αυτόν
                        self._show_originality(None)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    # ---------- εμφάνιση ----------
    def show_tab(self, name):
        self._finish_manual()
        self.tab = name
        for n, b in self.tab_btns.items():
            b.config(bg=ACCENT if n == name else PANEL, fg="white" if n == name else TEXT)
        self.render()

    def _view_insert(self, text, tags=()):
        self.text.config(state="normal")
        self.text.insert("end", text, tags)
        self.text.see("end")
        self.text.config(state="disabled")

    def render(self):
        """Δείχνει το κείμενο της καρτέλας με τίτλους, κουκκίδες, έντονα και τύπους."""
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        md = self.out[self.tab]
        if not md:
            hint = ("Το βοήθημα, η λύση ή η εργασία εμφανίζεται εδώ." if self.tab == "Claude" else
                    f"Πάτα «{self.tab} ▶» για δεύτερη γνώμη πάνω στο ανοιχτό section.")
            self.text.insert("end", "\n\n" + hint, "muted")
        self.diagram_images = []  # το Tk χρειάζεται τις εικόνες να μένουν κάπου όσο φαίνονται
        for block, data in parse_blocks(md):
            if block == "diagram":
                self._insert_diagram(data)
            elif block == "table":
                self._insert_table(data)
            else:
                kind, txt = line_kind(data.strip())
                if kind == "-":
                    self.text.insert("end", "•  ", kind)
                for part, style in inline_parts(txt):
                    self.text.insert("end", part, (kind, style) if style else kind)
                self.text.insert("end", "\n", kind)
        self.text.config(state="disabled")

    def _insert_diagram(self, data):
        from PIL import ImageTk
        try:
            img = draw_diagram(*data)
        except Exception as e:  # ένα χαλασμένο σχεδιάγραμμα δεν πρέπει να κρύβει το υπόλοιπο κείμενο
            self.text.insert("end", f"[Το σχεδιάγραμμα δεν σχεδιάστηκε: {e}]\n", "muted")
            return
        # Το μέγεθος ακολουθεί τα «Γράμματα» και την οθόνη, αλλά δεν ξεπερνά το πλάτος του πεδίου
        scale = self.winfo_fpixels("1i") / 96 * self.size / 11 / 2
        width = min(img.width * scale, max(self.text.winfo_width() - 60, 300))
        photo = ImageTk.PhotoImage(img.resize((int(width), int(width * img.height / img.width))))
        self.diagram_images.append(photo)
        self.text.insert("end", "\n")
        self.text.image_create("end", image=photo, padx=6, pady=4)
        self.text.insert("end", "\n\n")

    def _insert_table(self, rows):
        """Πίνακας με στήλες στοιχισμένες (με tabs), επικεφαλίδα με έντονα και μπλε φόντο."""
        import tkinter.font as tkfont
        cols = max(len(r) for r in rows)
        rows = [[plain_line(v) for v in r] + [""] * (cols - len(r)) for r in rows]
        font = tkfont.Font(family="Segoe UI", size=self.size, weight="bold")
        widths = [max(font.measure(r[c]) for r in rows) + 30 for c in range(cols)]
        stops = [12 + sum(widths[:c + 1]) for c in range(cols - 1)]
        tag = f"table{len(self.diagram_images)}_{self.text.index('end')}"
        self.text.tag_config(tag, tabs=stops, lmargin1=12, lmargin2=12, spacing1=2, spacing3=2)
        for r, row in enumerate(rows):
            self.text.insert("end", "\t".join(row) + "\n", (tag, "th") if r == 0 else tag)

    # ---------- εξαγωγή / εκτύπωση ----------
    def _doc_title(self):
        name = self.names[self.tab]
        return name if self.tab == "Claude" else f"{name} ({self.tab})"

    def export_dir(self):
        """Βοήθημα → «Βοηθήματα», άσκηση → «Ασκήσεις», εργασία → «Εργασίες»· αλλιώς ο κεντρικός φάκελος."""
        return self.folders.get(self.kinds.get(self.tab), self.folders["base"])

    def export_menu(self):
        """Μικρό μενού κάτω από το κουμπί «Εξαγωγή»: σε ποιο είδος αρχείου."""
        m = tk.Menu(self, tearoff=0, font=("Segoe UI", 10))
        for fmt, (label, ext, _, icon) in EXPORT_FORMATS.items():
            m.add_command(label=f"  {label} ({ext})", image=self.icon(icon, 16) or "", compound="left",
                          command=lambda f=fmt: self.export(f))
        b = self.export_btn
        m.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())

    def export(self, fmt="pdf"):
        self._finish_manual()
        if not self.out[self.tab]:
            messagebox.showinfo("Εξαγωγή", "Δεν υπάρχει ακόμα κείμενο σε αυτή την καρτέλα.")
            return
        label, ext, func, _ = EXPORT_FORMATS[fmt]
        path = filedialog.asksaveasfilename(title=f"Αποθήκευση ως {label}", initialfile=self._doc_title() + ext,
                                            initialdir=self.export_dir(), defaultextension=ext,
                                            filetypes=[(label, "*" + ext)])
        if not path:
            return
        try:
            globals()[func](self.out[self.tab], path)
        except OSError as e:  # π.χ. το αρχείο είναι ανοιχτό στο Word/Excel
            messagebox.showerror("Εξαγωγή", f"Δεν αποθηκεύτηκε — μήπως είναι ανοιχτό σε άλλο πρόγραμμα;\n{e}")
            return
        self.set_status(f"Αποθηκεύτηκε: {path}", "green")

    def print_pdf(self):
        self._finish_manual()
        if not self.out[self.tab]:
            messagebox.showinfo("Εκτύπωση", "Δεν υπάρχει ακόμα κείμενο σε αυτή την καρτέλα.")
            return
        path = os.path.join(tempfile.gettempdir(), f"XrysaStudy - {self._doc_title()}.pdf")
        export_pdf(self.out[self.tab], path)
        try:
            os.startfile(path, "print")
            self.set_status("Στάλθηκε στον εκτυπωτή.", "green")
        except OSError:
            # Αν το πρόγραμμα PDF δεν υποστηρίζει απευθείας εκτύπωση, το ανοίγουμε για Ctrl+P
            os.startfile(path)
            self.set_status("Άνοιξε το PDF — πάτα Ctrl+P για εκτύπωση.")


def selftest():
    """Γρήγορος έλεγχος χωρίς σύνδεση στο internet: αρχεία, μετατροπές, μορφοποίηση, PDF και παράθυρο."""
    import docx
    from openpyxl import Workbook
    from PIL import Image
    from pptx import Presentation
    tmp = tempfile.gettempdir()

    xlsx = os.path.join(tmp, "xrysastudy_test.xlsx")
    wb = Workbook()
    wb.active.title = "Βαθμοί"
    wb.active["A1"], wb.active["B1"], wb.active["B2"] = "Όνομα", "Βαθμός", 8
    wb.save(xlsx)
    assert "A1=Όνομα  B1=Βαθμός" in read_excel(xlsx) and "B2=8" in read_excel(xlsx)

    docx_path = os.path.join(tmp, "xrysastudy_test.docx")
    d = docx.Document()
    d.add_paragraph("Υπολόγισε τον μέσο όρο.")
    d.save(docx_path)
    assert "μέσο όρο" in file_block(docx_path)["text"]

    pptx_path = os.path.join(tmp, "xrysastudy_test.pptx")
    p = Presentation()
    p.slides.add_slide(p.slide_layouts[1]).shapes.title.text = "Πρωτεΐνες"
    p.save(pptx_path)
    assert "Διαφάνεια 1:\nΠρωτεΐνες" in read_pptx(pptx_path)

    png = os.path.join(tmp, "xrysastudy_test.png")
    Image.new("RGB", (4, 4), "white").save(png)
    img = file_block(png)
    assert img["type"] == "image" and img["source"]["media_type"] == "image/png"

    pdf_block = {"type": "document", "title": "a.pdf", "source": {"media_type": "application/pdf", "data": "QQ=="}}
    items = to_openai_items([{"type": "text", "text": "γεια"}, img, pdf_block])
    assert [i["type"] for i in items] == ["input_text", "input_image", "input_file"]
    assert items[2]["file_data"] == "data:application/pdf;base64,QQ==" and items[2]["filename"] == "a.pdf"
    parts = to_gemini_parts([{"type": "text", "text": "γεια"}, pdf_block])
    assert parts[0].text == "γεια" and parts[1].inline_data.mime_type == "application/pdf"

    assert line_kind("## Τίτλος") == ("##", "Τίτλος")
    assert list(inline_parts("**α** και `=SUM(A1)`")) == [("α", "b"), (" και ", ""), ("=SUM(A1)", "code")]
    assert inline_html("**α** & `<x>`") == '<b>α</b> &amp; <font name="Consolas">&lt;x&gt;</font>'

    sample = "# Δοκιμή\n## Βήμα 1\n- Γράψε `=AVERAGE(B2:B20)` στο **C2** & <πάτα Enter>\nΑπλό κείμενο."
    pdf = os.path.join(tmp, "xrysastudy_selftest.pdf")
    export_pdf(sample, pdf)
    assert os.path.getsize(pdf) > 1000, "Το PDF βγήκε άδειο"

    # Σχεδιαγράμματα και πίνακες: αναγνώριση, σχέδιο και εξαγωγή
    rich = ("# Αμινοξέα\n[ΔΙΑΓΡΑΜΜΑ: Σύνθεση]\nDNA -> mRNA -> Πρωτεΐνη : μετάφραση\nΠρωτεΐνη -> DNA\n[/ΔΙΑΓΡΑΜΜΑ]\n"
            "| Αμινοξύ | Σύμβολο |\n|---|---|\n| Γλυκίνη | Gly |\nΤέλος.")
    blocks = parse_blocks(rich)
    assert [b[0] for b in blocks] == ["line", "diagram", "table", "line"]
    assert blocks[1][1] == ("Σύνθεση", ["DNA", "mRNA", "Πρωτεΐνη"],
                            [("DNA", "mRNA", "μετάφραση"), ("mRNA", "Πρωτεΐνη", "μετάφραση"), ("Πρωτεΐνη", "DNA", "")])
    assert blocks[2][1] == [["Αμινοξύ", "Σύμβολο"], ["Γλυκίνη", "Gly"]]
    picture = draw_diagram(*blocks[1][1])
    assert picture.width > 300 and picture.height > 100
    rich_pdf, rich_docx, rich_txt = (os.path.join(tmp, f"xrysastudy_rich{e}") for e in (".pdf", ".docx", ".txt"))
    export_pdf(rich, rich_pdf)
    export_docx(rich, rich_docx)
    rich_doc = docx.Document(rich_docx)
    assert len(rich_doc.inline_shapes) == 1 and rich_doc.tables[0].cell(1, 1).text == "Gly"
    export_txt(rich, rich_txt)
    with open(rich_txt, encoding="utf-8-sig") as f:
        assert "[Σχεδιάγραμμα: Σύνθεση]\nDNA → mRNA (μετάφραση)" in f.read()

    # Εξαγωγή σε Word, Excel και κείμενο
    md = "# Εργασία\n## Εισαγωγή\n- Ο **σίδηρος** είναι απαραίτητος.\n=SUM(A1:A3) σε απλό κείμενο"
    docx_out, xlsx_out, txt_out = (os.path.join(tmp, f"xrysastudy_export{e}") for e in (".docx", ".xlsx", ".txt"))
    export_docx(md, docx_out)
    paras = docx.Document(docx_out).paragraphs
    assert paras[0].style.name == "Heading 1" and paras[1].style.name == "Heading 2"
    assert paras[2].style.name == "List Bullet" and paras[2].runs[1].bold and paras[2].text == "Ο σίδηρος είναι απαραίτητος."
    export_xlsx(md, xlsx_out)
    from openpyxl import load_workbook
    ws = load_workbook(xlsx_out).active
    assert ws["A1"].value == "Εργασία" and ws["A1"].font.bold and ws["A3"].value == "• Ο σίδηρος είναι απαραίτητος."
    assert ws["A4"].value == "=SUM(A1:A3) σε απλό κείμενο" and ws["A4"].data_type == "s"
    export_txt(md, txt_out)
    with open(txt_out, encoding="utf-8-sig") as f:
        assert f.read() == "Εργασία\nΕισαγωγή\n• Ο σίδηρος είναι απαραίτητος.\n=SUM(A1:A3) σε απλό κείμενο"

    # Πρωτοτυπία: 8+ ίδιες λέξεις (ακόμα και με διαφορετικούς τόνους/κεφαλαία) βρίσκονται, οι λίγες όχι
    src = {"Σημειώσεις.pdf": "Η μεσογειακή διατροφή μειώνει σημαντικά τον κίνδυνο καρδιαγγειακών νοσημάτων στους ενήλικες."}
    essay = "Εισαγωγή. Όπως φαίνεται, η Μεσογειακή διατροφη μειώνει σημαντικά τον κίνδυνο καρδιαγγειακών νοσημάτων. Τέλος."
    spans, pct = find_copied(essay, src)
    assert len(spans) == 1 and essay[spans[0][0]:spans[0][1]] == "η Μεσογειακή διατροφη μειώνει σημαντικά τον κίνδυνο καρδιαγγειακών νοσημάτων"
    assert spans[0][2] == "Σημειώσεις.pdf" and pct == 69  # 9 από τις 13 λέξεις
    assert find_copied("Η μεσογειακή διατροφή είναι καλή.", src) == ([], 0)
    assert strip_references("Κείμενο\nΒιβλιογραφία\nSmith (2020)") == "Κείμενο\n"
    assert ORIG_BLOCK.findall("<<<ΚΟΜΜΑΤΙ\nμια πρόταση\n===\nΠηγή: Α · Γιατί: μετάφραση\n>>>") == [
        ("μια πρόταση", "Πηγή: Α · Γιατί: μετάφραση")]
    assert source_text(docx_path) == "Υπολόγισε τον μέσο όρο." and source_text(png) == ""

    assert friendly_error("Gemini", Exception("429 RESOURCE_EXHAUSTED. quota")).startswith("Τελείωσε το δωρεάν όριο")
    assert "κλειδί του Gemini δεν είναι σωστό" in friendly_error("Gemini", Exception("400 API key not valid"))
    assert friendly_error("Claude", Exception("κάτι άλλο")) == "Claude: κάτι άλλο"
    assert friendly_error("Claude", SourceError("Δεν βρέθηκαν άρθρα.")) == "Δεν βρέθηκαν άρθρα."

    # Κόστος: 8.000 tokens διαβάσματος + 5.000 γραψίματος στο Claude = 0,016 + 0,05 = 0,066$
    assert abs(cost_of("Claude", {"in": 8000, "out": 5000}) - 0.066) < 1e-9
    assert cost_of("Gemini", {"in": 8000, "out": 5000}) == 0
    c = add_cost({}, 0.066, datetime.date(2026, 10, 26), 13000)
    c = add_cost(c, 0.034, datetime.date(2026, 10, 26), 7000)
    assert round(c["today"], 3) == 0.1 and round(c["month_total"], 3) == 0.1 and c["last"] == 0.034
    assert (c["last_tokens"], c["today_tokens"], c["month_tokens"]) == (7000, 20000, 20000)
    c = add_cost(c, 0.05, datetime.date(2026, 10, 27), 5000)  # νέα μέρα: το «Σήμερα» ξεκινά από την αρχή
    assert c["today"] == 0.05 and round(c["month_total"], 3) == 0.15 and c["today_tokens"] == 5000
    c = add_cost(c, 0.01, datetime.date(2026, 11, 1), 1000)   # νέος μήνας
    assert c["month_total"] == 0.01 and c["month_tokens"] == 1000
    old = add_cost({"day": "2026-10-26", "today": 0.1, "month": "2026-10", "month_total": 0.1},
                   0.0, datetime.date(2026, 10, 26), 500)  # ρυθμίσεις της v0.11, χωρίς tokens
    assert old["today_tokens"] == 500
    assert money(0.0684) == "0,068$" and money(2.1) == "2,10$" and count_fmt(1234567) == "1.234.567"

    # Επιστημονικές πηγές (χωρίς internet)
    xml = b"""<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID><Article>
      <Journal><JournalIssue><PubDate><Year>2021</Year></PubDate></JournalIssue><Title>Nutrients</Title></Journal>
      <ArticleTitle>Olive oil and <i>health</i>.</ArticleTitle>
      <Abstract><AbstractText>First part.</AbstractText><AbstractText>Second part.</AbstractText></Abstract>
      <AuthorList><Author><LastName>Smith</LastName><Initials>J</Initials></Author></AuthorList></Article></MedlineCitation>
      <PubmedData><ArticleIdList><ArticleId IdType="doi">10.1/abc</ArticleId></ArticleIdList></PubmedData>
      </PubmedArticle></PubmedArticleSet>"""
    art = parse_pubmed(xml)[0]
    assert art == {"title": "Olive oil and health.", "authors": ["Smith J"], "year": "2021", "journal": "Nutrients",
                   "doi": "10.1/abc", "pmid": "123", "abstract": "First part. Second part."}
    assert openalex_abstract({"world": [1], "Hello": [0]}) == "Hello world"
    listed = format_sources([art])
    assert listed.startswith("[1] Smith J (2021). Olive oil and health. Nutrients. DOI: https://doi.org/10.1/abc | "
                             "PubMed: https://pubmed.ncbi.nlm.nih.gov/123/")

    # Φάκελοι: δημιουργούνται οι τέσσερις υποφάκελοι μέσα στον κεντρικό
    assert os.path.isdir(documents_dir())
    test_base = os.path.join(tmp, "xrysastudy_folders_test")
    folders = ensure_folders(test_base)
    assert all(os.path.isdir(os.path.join(test_base, name)) for name in FOLDER_NAMES.values())
    assert folders["essay"] == os.path.join(test_base, "Εργασίες") and folders["base"] == test_base

    app = App()
    app.kinds["Claude"] = "exercise"
    app.tab = "Claude"
    assert app.export_dir() == app.folders["exercise"]
    app.tab = "Gemini"  # καρτέλα χωρίς αποτέλεσμα: ο κεντρικός φάκελος
    assert app.export_dir() == app.folders["base"]
    app.cfg["keys"]["ChatGPT"] = ""
    app.refresh_providers()
    assert str(app.tab_btns["ChatGPT"]["state"]) == "disabled"
    app.cfg["keys"]["ChatGPT"] = "sk-test"
    app.refresh_providers()
    assert str(app.opinion_btns["ChatGPT"]["state"]) == "normal"

    # Sections: ένα ανοιχτό τη φορά, ξανά πάτημα το κλείνει
    app.toggle_section("study")
    app.toggle_section("essay")
    app.update()
    assert app.section == "essay" and app.panels["essay"].winfo_ismapped() and not app.panels["study"].winfo_ismapped()
    app.toggle_section("essay")
    assert app.section is None

    # Εργασίες κάθε section (χωρίς να αποθηκευτούν στις ρυθμίσεις της χρήστριας)
    app.files = {"study": [pdf], "exercise": [xlsx], "essay": []}
    app.level.set("detailed")
    system, content, name = app.build_task("study")
    assert "ΑΝΑΛΥΤΙΚΟ" in system and content[0]["type"] == "document" and name == "xrysastudy_selftest - βοήθημα"
    app.boxes["exercise"].insert("1.0", "Βρες τον μέσο όρο.")
    system, content, _ = app.build_task("exercise")
    assert "B2=8" in content[1]["text"] and content[-1]["text"].endswith("Βρες τον μέσο όρο.")
    app.boxes["essay"].insert("1.0", "Μεσογειακή διατροφή")
    system, content, name = app.build_task("essay")
    assert system.startswith(ESSAY_PROMPT) and name == "Εργασία" and "Μεσογειακή" in content[-1]["text"]

    # Μορφή παραπομπών: έτοιμη μορφή ή δικό μου παράδειγμα
    assert citation_rule({"citation_style": "Vancouver"}).startswith("ΜΟΡΦΗ ΠΑΡΑΠΟΜΠΩΝ: Vancouver")
    assert citation_rule({}) == "ΜΟΡΦΗ ΠΑΡΑΠΟΜΠΩΝ: " + CITATION_STYLES["APA 7"]
    custom = citation_rule({"citation_style": CUSTOM_STYLE, "citation_example": "(Παπαδόπουλος, 2020, σ. 15)"})
    assert "ΑΚΡΙΒΩΣ" in custom and custom.endswith("(Παπαδόπουλος, 2020, σ. 15)")
    assert citation_rule({"citation_style": CUSTOM_STYLE, "citation_example": ""}).endswith(CITATION_STYLES["APA 7"])
    app.cfg["citation_style"] = "IEEE"
    assert app.build_task("essay")[0].endswith(CITATION_STYLES["IEEE"])

    # «Από επίσημες πηγές»: τα άρθρα μπαίνουν πρώτα και προστίθενται οι κανόνες παραπομπών
    global stream_reply, find_sources
    real = stream_reply, find_sources
    stream_reply = lambda *a: iter(["1. mediterranean diet\n2. olive oil health"])
    find_sources = lambda queries: [art] if queries == ["mediterranean diet", "olive oil health"] else []
    try:
        s2, msgs = app._add_sources("Μεσογειακή διατροφή", "Claude", "k", "m", system, [{"role": "user", "content": content}])
    finally:
        stream_reply, find_sources = real
    assert s2.endswith(CITATION_NOTE) and msgs[0]["content"][0]["text"].startswith("=== ΕΠΙΣΤΗΜΟΝΙΚΑ ΑΡΘΡΑ ===\n[1] Smith J")

    app.cfg["instructions"] = "Λύνε με συναρτήσεις."
    app.only["exercise"].set(True)
    s = app.system_for("ΒΑΣΗ", "exercise")
    assert s.startswith("ΒΑΣΗ") and "Λύνε με συναρτήσεις." in s and "ΑΥΣΤΗΡΟΣ ΚΑΝΟΝΑΣ" in s
    app.cfg["instructions"] = ""
    plain = "ΒΑΣΗ\n\n" + GREEK_RULE
    assert app.system_for("ΒΑΣΗ", "essay") == plain and app.system_for("ΒΑΣΗ", None) == plain

    # Αυτόματος ορθογραφικός έλεγχος: μόλις τελειώσει νέο αποτέλεσμα, ξεκινά έλεγχος στην ίδια καρτέλα
    calls = []
    app.ask = lambda *a, **k: calls.append(a) or True
    app.autoproof.set(True)
    app.out["Claude"], app.jobs["Claude"] = "κείμενο", "doc"
    app.q.put(("Claude", "done", None))
    app._poll()
    assert calls[0][0] == "Claude" and calls[0][2] == PROOF_PROMPT and app.backup["Claude"] == "κείμενο"
    app.q.put(("Claude", "done", None))  # ο έλεγχος τελείωσε: δεν ξεκινά δεύτερος
    app._poll()
    assert len(calls) == 1
    app.autoproof.set(False)

    # «✏ Αλλαγές»: εφαρμόζονται μόνο τα σημεία που ζητήθηκαν, το υπόλοιπο κείμενο μένει ίδιο
    reply = ("<<<ΒΡΕΣ\n## Βήμα 1\n===\n## Βήμα 1\n- Νέα γραμμή εδώ\n>>>\n"
             "<<<ΒΡΕΣ\nΑπλό κείμενο.\n===\n>>>\n<<<ΒΡΕΣ\nδεν υπάρχει\n===\nτίποτα\n>>>")
    assert parse_edits(reply)[1] == ("Απλό κείμενο.", "")
    new, applied, failed = apply_edits(sample, parse_edits(reply))
    assert new == sample.replace("## Βήμα 1", "## Βήμα 1\n- Νέα γραμμή εδώ").replace("Απλό κείμενο.", "")
    assert len(applied) == 2 and failed == 1
    calls.clear()
    app.out["Claude"], app.backup = sample, {}
    app.show_tab("Claude")
    app.edit_entry.insert(0, "πρόσθεσε μια γραμμή")
    app.request_edit()
    assert calls[0][0] == "edit" and calls[0][3][0]["content"][-1]["text"].endswith("πρόσθεσε μια γραμμή")
    app.edit_tab, app.edit_reply = "Claude", reply
    app.q.put(("edit", "done", None))
    app._poll()
    assert app.out["Claude"] == new and app.backup["Claude"] == sample
    assert app.text.tag_ranges("changed"), "οι αλλαγές δεν φωτίστηκαν"
    del app.ask

    # Δεξί κλικ: στο αποτέλεσμα (μόνο ανάγνωση) δεν υπάρχει επικόλληση· στα κουτιά γραψίματος υπάρχουν όλα
    menu = app._edit_menu(app.text)
    assert menu.entrycget(1, "label") == "Αντιγραφή" and menu.entrycget(2, "state") == "disabled"
    assert app._edit_menu(app.chat_entry).entrycget(2, "state") == "normal"
    app.chat_entry.insert(0, "γεια σου")
    app._select_all(app.chat_entry)
    assert app.chat_entry.selection_get() == "γεια σου"
    app.chat_entry.delete(0, "end")

    # Χειροκίνητη επεξεργασία: ό,τι γράφεις αποθηκεύεται, και το «Αρχικό» το αναιρεί
    app.out["Claude"], app.backup = "# Τίτλος\nκείμενο", {}
    app.show_tab("Claude")
    app.toggle_manual()
    assert app.editing == "Claude" and app.text.get("1.0", "end-1c") == "# Τίτλος\nκείμενο"
    app.text.insert("end", "\nνέα γραμμή")
    app.toggle_manual()
    assert app.editing is None and app.out["Claude"] == "# Τίτλος\nκείμενο\nνέα γραμμή"
    assert app.backup["Claude"] == "# Τίτλος\nκείμενο" and str(app.text["state"]) == "disabled"

    # Σχεδιάγραμμα και πίνακας στην οθόνη· «Αλλαγές» χωρίς αλλαγές δείχνουν την απάντηση του Claude
    app.out["Claude"] = rich
    app.show_tab("Claude")
    assert len(app.diagram_images) == 1 and "Γλυκίνη\tGly" in app.text.get("1.0", "end")
    app.edit_tab, app.edit_reply = "Claude", "Δεν μπορώ να βάλω εικόνες."
    app._apply_edit()
    assert app.out["Claude"] == rich
    for w in app.winfo_children():
        if isinstance(w, tk.Toplevel):
            w.destroy()

    # Πρωτοτυπία μέσα στο πρόγραμμα: κόκκινο στα αυτούσια, πορτοκαλί σε ό,τι βρει το Claude, και αναφορά
    calls.clear()
    app.ask = lambda *a, **k: calls.append(a) or True
    app.files["essay"], app.kinds["Claude"], app.sources = [txt_out], "essay", {}
    app.out["Claude"] = "## Εισαγωγή\nΟ σίδηρος είναι απαραίτητος. Το νερό κάνει καλό στην υγεία μας."
    app.show_tab("Claude")
    app.check_originality()
    assert calls[-1][0] == "orig" and app.orig_ctx["pct"] == 0  # 4 ίδιες λέξεις δεν φτάνουν για αντιγραφή
    app.orig_reply = "<<<ΚΟΜΜΑΤΙ\nΟ σίδηρος είναι απαραίτητος.\n===\nΠηγή: x · Γιατί: ίδιο νόημα\n>>>"
    app.busy.add("orig")
    app.q.put(("orig", "done", None))
    app._poll()
    assert app.text.tag_ranges("close") and app.orig_ctx is None
    for w in app.winfo_children():  # κλείνει το παράθυρο της αναφοράς
        if isinstance(w, tk.Toplevel):
            w.destroy()
    del app.ask

    # Chat ως πλαίσιο, «Παράθυρο» / «Επιστροφή» και πρόταση μεγέθους εμφάνισης
    panes = lambda: list(map(str, app.body.panes()))
    box = app.detachables
    app.toggle_section("essay")
    app.toggle_chat()
    app.update()
    assert panes() == [str(app.side), str(box["essay"]), str(box["chat"]), str(app.right)]
    app.toggle_detach("essay")
    app.update()
    assert "essay" in app.detached and str(box["essay"]) not in panes() and box["essay"].winfo_viewable()
    assert app.tk.call("wm", "title", box["essay"]._w) == "XrysaStudy — Εργασία"
    app.toggle_detach("essay")  # επιστροφή: ξανά πριν από το Chat
    app.update()
    assert "essay" not in app.detached and panes()[1:3] == [str(box["essay"]), str(box["chat"])]
    app.toggle_detach("result")
    app.update()
    assert str(box["result"]) not in map(str, app.right.panes()) and box["result"].winfo_viewable(), "το παράθυρο δεν φάνηκε"
    app.toggle_detach("result")
    assert str(box["result"]) in map(str, app.right.panes())
    app.toggle_detach("essay")
    app.toggle_section("essay")  # κλείσιμο ενώ είναι σε ξεχωριστό παράθυρο
    app.toggle_chat()
    app.update()
    assert app.section is None and not app.detached and panes() == [str(app.side), str(app.right)]
    zoom, screen = app.suggest_zoom()
    assert 0.7 <= zoom <= 1.3 and screen.startswith("Οθόνη ")
    assert app.icon("💬", 46, "Chat") is not None

    # Μηδενισμός κόστους (χωρίς να πειραχτούν οι πραγματικές ρυθμίσεις)
    global save_config
    real_save, real_ask = save_config, messagebox.askyesno
    save_config, messagebox.askyesno = (lambda cfg: None), (lambda *a, **k: True)
    try:
        app.cfg["costs"] = add_cost({}, 0.5, datetime.date.today(), 1000)
        app.reset_cost()
        assert (app.cfg["costs"]["today"], app.cfg["costs"]["month_tokens"], app.cfg["costs"]["last"]) == (0.0, 0, 0.0)
        assert app.cost_label["text"].startswith("Τελευταίο 0,000$ (0)")
    finally:
        save_config, messagebox.askyesno = real_save, real_ask

    # Εικονίδια, έκδοση και ιστορικό αλλαγών
    assert app.icon("📘", 16) is not None, "δεν βγήκαν τα χρωματιστά εικονίδια"
    assert version_tuple("v0.14") == (0, 14) and version_tuple("0.14") > version_tuple("0.9")
    assert f"## {VERSION}" in read_changelog(), "λείπει η τρέχουσα έκδοση από το CHANGELOG.md"

    app.out["Claude"] = sample
    app.show_tab("Gemini")
    app.show_tab("Claude")
    app.backup["Claude"] = "αρχικό"
    app.undo_humanize()
    assert app.out["Claude"] == "αρχικό"
    app.destroy()
    print("OK")


def run_selftest():
    """Ο έλεγχος και μέσα στο .exe: εκεί δεν υπάρχει παράθυρο εντολών, οπότε το λάθος γράφεται σε αρχείο
    και το αποτέλεσμα φαίνεται από τον κωδικό εξόδου (0 = όλα καλά)."""
    import traceback
    log = os.path.join(tempfile.gettempdir(), "xrysastudy_selftest.log")
    try:
        selftest()
    except BaseException:
        with open(log, "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        print(f"Ο έλεγχος απέτυχε — δες το {log}")
        sys.exit(1)


if __name__ == "__main__":
    run_selftest() if "--selftest" in sys.argv else App().mainloop()
