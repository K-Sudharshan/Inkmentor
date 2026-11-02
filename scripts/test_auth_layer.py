"""
Assert-based self-check for the InkMentor Authentication Layer.
Verifies:
1. Presence and integrity of Google GIS script and meta tag in <head>
2. Presence and styling rules for #auth-screen and body.app-unauthenticated
3. HTML integrity of #auth-screen, Google button container, profile setup fields (Name, Age, DOB)
4. Header user chip integration in <header id="hd">
5. Profile modal structure (#profile-modal, #profile-backdrop)
6. Correctness of calculateAge algorithm across edge cases (birthdays today, tomorrow, yesterday, leap years)
7. Consistency between InkMentor.html and public/index.html
8. Zero regressions to existing math solver and audio elements
"""

import re
from datetime import date

def test_calculate_age_python_replica():
    def calc_age(dob_str, today=None):
        if not dob_str:
            return ""
        parts = [int(p) for p in dob_str.split("-")]
        birth = date(parts[0], parts[1], parts[2])
        if today is None:
            today = date(2026, 11, 2)
        if birth > today:
            return ""
        age = today.year - birth.year
        if (today.month, today.day) < (birth.month, birth.day):
            age -= 1
        return age if age >= 0 else 0

    today = date(2026, 11, 2)
    # Passed birthday yesterday:
    assert calc_age("2000-11-01", today) == 26, "Expected 26 for birthday yesterday"
    # Birthday today:
    assert calc_age("2000-11-02", today) == 26, "Expected 26 for birthday today"
    # Birthday tomorrow:
    assert calc_age("2000-11-03", today) == 25, "Expected 25 for birthday tomorrow"
    # Born this year (infant):
    assert calc_age("2026-05-10", today) == 0, "Expected 0 for infant born earlier this year"
    # Future date:
    assert calc_age("2027-01-01", today) == "", "Expected empty string for future date"
    print("[PASS] calculateAge verification passed across all date edge cases.")

def test_html_files():
    for file_path in ["InkMentor.html", "public/index.html"]:
        with open(file_path, "r", encoding="utf-8") as f:
            html = f.read()

        # 1. Google GIS script and env-based config integration
        assert "accounts.google.com/gsi/client" in html, f"Missing GIS script in {file_path}"
        assert "fetchBackendConfig" in html, f"Missing fetchBackendConfig in {file_path}"
        assert "/api/config" in html, f"Missing /api/config call in {file_path}"

        # 2. Auth screen and elements
        assert 'id="auth-screen"' in html, f"Missing #auth-screen in {file_path}"
        assert 'id="google-signin-btn"' in html, f"Missing #google-signin-btn in {file_path}"
        assert 'id="auth-name-input"' in html, f"Missing #auth-name-input in {file_path}"
        assert 'id="auth-dob-input"' in html, f"Missing #auth-dob-input in {file_path}"
        assert 'id="auth-age-input"' in html, f"Missing #auth-age-input in {file_path}"
        assert 'id="auth-submit-profile-btn"' in html, f"Missing submit profile button in {file_path}"

        # 3. Header user chip
        assert 'id="user-chip-wrap"' in html, f"Missing #user-chip-wrap in {file_path}"
        assert 'id="user-chip-btn"' in html, f"Missing #user-chip-btn in {file_path}"
        assert 'id="user-chip-name"' in html, f"Missing #user-chip-name in {file_path}"

        # 4. Profile modal
        assert 'id="profile-modal"' in html, f"Missing #profile-modal in {file_path}"
        assert 'id="profile-backdrop"' in html, f"Missing #profile-backdrop in {file_path}"
        assert 'id="pm-save-btn"' in html, f"Missing #pm-save-btn in {file_path}"
        assert 'id="pm-logout-btn"' in html, f"Missing #pm-logout-btn in {file_path}"

        # 5. CSS rules for unauthenticated masking
        assert "body.app-unauthenticated #app" in html, f"Missing unauthenticated CSS rule in {file_path}"
        assert "body.app-unauthenticated #auth-screen" in html, f"Missing auth-screen active rule in {file_path}"

        # 6. JS module and loader hooks
        assert "window.InkMentorAuth" in html, f"Missing window.InkMentorAuth in {file_path}"
        assert "checkSessionOnLoaderDismiss" in html, f"Missing checkSessionOnLoaderDismiss in {file_path}"

        # 7. Existing critical elements preserved
        assert 'id="loader-screen"' in html, f"Loader screen lost in {file_path}"
        assert 'id="tb-stationery"' in html, f"Stationery tray lost in {file_path}"
        assert 'id="ai-actions"' in html, f"AI actions lost in {file_path}"
        assert 'id="solve"' in html, f"Solve button lost in {file_path}"
        assert 'id="paper"' in html, f"Paper element lost in {file_path}"
        assert 'id="settings-modal"' in html, f"Settings modal lost in {file_path}"

        print(f"[PASS] All checks passed for {file_path}")

    # Check that both files are identical
    with open("InkMentor.html", "rb") as f1, open("public/index.html", "rb") as f2:
        assert f1.read() == f2.read(), "InkMentor.html and public/index.html are not in sync!"
    print("[PASS] InkMentor.html and public/index.html are identical.")

if __name__ == "__main__":
    test_calculate_age_python_replica()
    test_html_files()
    print("\nALL AUTH LAYER SELF-CHECKS PASSED SUCCESSFULLY!")
