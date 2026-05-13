IMPORT_TERMINATOR_SEQUENCES = [
    "AGGRESSION_FACTOR", "TOXIN", "VENOM", "BOTULINUM", "RICIN",
    "ANTHRAX", "SMALLPOX", "EBOLA", "Marburg",
    "SEQUENCE_IMPORT", "EXPORT_CONTROL",
]

SENSITIVE_PATTERNS = [
    "CGGCGG", "CCGGCC", "GGCCGG",
]

DUAL_USE_CATEGORIES = {
    "enhanced_pathogenicity": "Sequence could enhance pathogen virulence",
    "immune_evasion": "Sequence could help pathogens evade immune response",
    "toxin_activity": "Sequence has homology to known toxin domains",
    "host_range_adaptation": "Sequence could expand host range of pathogens",
}


class ComplianceChecker:
    def __init__(self):
        self.restricted_sequences = IMPORT_TERMINATOR_SEQUENCES

    def check_dual_use(self, sequence: str) -> dict:
        flags = []
        for term in self.restricted_sequences:
            if term in sequence.upper():
                flags.append({
                    "category": "restricted_terminator",
                    "detail": f"Sequence contains restricted terminator: {term}",
                    "severity": "critical",
                })

        for category, description in DUAL_USE_CATEGORIES.items():
            for pattern in SENSITIVE_PATTERNS:
                if pattern in sequence.upper():
                    flags.append({
                        "category": category,
                        "detail": description,
                        "severity": "warning" if category != "toxin_activity" else "critical",
                    })

        return {
            "is_sensitive": len(flags) > 0,
            "flags": flags,
            "disclaimer": "For research use only. Not a medical device. "
                          "Candidates must undergo wet-lab validation.",
            "dual_use_assessment": "Sensitive" if flags else "Not Sensitive",
        }

    def get_disclaimer(self) -> str:
        return (
            "FOR RESEARCH USE ONLY. Not a medical device. "
            "Designed protein sequences are computational predictions only "
            "and must undergo wet-lab validation. "
            "This tool is not intended for diagnostic or therapeutic use."
        )
