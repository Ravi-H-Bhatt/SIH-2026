"""
Demonstrates exactly which MRZ edits our check-digit verification catches.

Answers: "if someone changes the name, must they change the MRZ too?"
"""

from app.services.ocr.mrz import calculate_check_digit as cd
from app.services.ocr.mrz import parse_mrz_lines

L1 = "P<INDDOE<<JOHN<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
L2 = "P1234567<1IND9001011M3110153<<<<<<<<<<<<<<06"
#     0.......8 9  10 13....18 19 21...26 27      42 43
#     docnum    CD nat  dob    CD  expiry CD  opt  CD composite


def verdict(label, l1, l2):
    r = parse_mrz_lines(l1 + "\n" + l2)
    ok = r.get("mrz_valid")
    print(label)
    print(f"    name = {r.get('holder_name')}   dob = {r.get('date_of_birth')}")
    print(f"    mrz_valid = {ok}  ->  " + ("ACCEPTED (we do NOT catch it)" if ok else "REJECTED (we catch it)"))
    print()


def composite_of(line2: str) -> int:
    """ICAO composite digit covers line-2 fields only, never line 1."""
    return cd(line2[0:10] + line2[13:20] + line2[21:43])


print("=" * 72)
verdict("0) GENUINE DOCUMENT", L1, L2)

# ── ATTACK A: change only the NAME (line 1). Line 2 untouched. ──────────────
print("=" * 72)
print("ATTACK A — change ONLY the holder name on line 1")
print("  The name lives on line 1. TD3 line 1 has NO check digit at all,")
print("  and the composite digit covers line 2 only. So NOTHING to recompute.")
print()
verdict("A) NAME changed: DOE JOHN -> KHAN IMRAN, line 2 untouched",
        "P<INDKHAN<<IMRAN<<<<<<<<<<<<<<<<<<<<<<<<<<<<", L2)

# ── ATTACK B: change DOB, fix only that field's digit, leave composite stale ─
print("=" * 72)
print("ATTACK B — change DOB, fix only its own check digit (pos 19)")
new_dob = "850101"
tampered = L2[:13] + new_dob + str(cd(new_dob)) + L2[20:]
print(f"  genuine  line2 : {L2}")
print(f"  tampered line2 : {tampered}")
print(f"  composite digit present = {tampered[43]}, "
      f"mathematically correct = {composite_of(tampered)}")
print("  -> the composite is now WRONG, but we never verify it.")
print()
verdict("B) DOB 1990 -> 1985, composite left stale", L1, tampered)

# ── ATTACK C: change DOB but forget the field digit -------------------------
print("=" * 72)
print("ATTACK C — change DOB and forget to fix its check digit (the lazy forger)")
lazy = L2[:13] + new_dob + L2[19:]
verdict("C) DOB changed, digit untouched", L1, lazy)

print("=" * 72)
print("SUMMARY")
print("  Name change              -> NOT caught by check digits (no digit protects line 1)")
print("  DOB/number/expiry change -> caught ONLY if the forger forgets the field digit")
print("  Composite digit          -> we read it but never verify it (a real gap)")
print("  What actually catches a name change: MRZ-vs-visual-zone comparison,")
print("  the ePassport chip (DG1 is hashed inside the signed SOD), or the face.")
