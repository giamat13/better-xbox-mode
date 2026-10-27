## Releasing xbox-mode

מאגר: `giamat13/better-xbox-mode`. ענף ברירת המחדל: `main`. מספר הגרסה נמצא ב-`package.json` (שדה `"version"`) והוא מקור האמת היחיד; `npm version` מעדכן גם את `package-lock.json`. פורמט התג: `vX.Y.Z`. תהליך השחרור: `.github/workflows/release.yml` (השם `release`). כל שחרור מפרסם ארבעה קבצים: `xbox-mode-X.Y.Z-setup.exe` (מתקין), `xbox-mode-X.Y.Z-portable.exe` (portable, בלי התקנה), `xbox-mode-X.Y.Z-setup.exe.blockmap` ו-`latest.yml`. שני האחרונים הם מה שהעדכון האוטומטי של המתקין קורא.

## כללים

1. **לא משחררים לפני שהשינוי ידוע כעובד.** הבדיקות המקומיות עוברות, ונבדקה הרצה של התוכנה עם בקר XInput אמיתי ב-Windows (`npm run windowed`). Claude לא יכול לחבר בקר, לכן לפני ההפעלה שואלים את המשתמש אם הבדיקה עם הבקר בוצעה, ורושמים בהערות השחרור מה נבדק.
2. משחררים ישירות מ-`main`. לא יוצרים ענף חדש בלי אישור מפורש מהמשתמש בהודעה הנוכחית.
3. לא משחררים מעל הרצה של CI שידוע כאדומה.
4. אם שחרור פורסם ויש בו תקלה - מפרסמים גרסה חדשה עם התיקון (PATCH). לא מוחקים שחרור שפורסם, אלא אם המשתמש ביקש במפורש.
5. הטוקן של GitHub תמיד מגיע מ-`git credential fill`, ולעולם לא מודפס או נכתב לקובץ.
6. לא דוחפים תגים ידנית (`git push --tags`). התג נוצר על ידי תהליך השחרור.

## מספרי גרסה

MAJOR.MINOR.PATCH (סמנטי). בכל שחרור מעלים מספר אחד בלבד, והמספרים הנמוכים ממנו מתאפסים:

- **MAJOR** - שינוי שאינו תואם לגרסה הקודמת (למשל קובץ ההגדרות `%APPDATA%\xbox_mode\config.json` לא נקרא נכון אחרי עדכון).
- **MINOR** - תכונה חדשה (מסך, כפתור, אפשרות).
- **PATCH** - תיקון באג בלבד.
- הגרסה הראשונה היא `1.0.0`. מספר שכבר יש לו תג לא משמש שוב.
- גרסת התוסף לדפדפן (`extension/manifest.json`) נפרדת: שחרור של התוכנה לא משנה אותה.
- אין גרסאות טרום-שחרור (pre-release).

## הערות שחרור

קובץ: `docs/release-notes-vX.Y.Z.md` (הוא הופך לגוף השחרור ב-GitHub). התיקייה `docs/` נוצרת אם חסרה. הקובץ חייב להתקיים לפני ההפעלה: התהליך נכשל בלעדיו. סעיפים לפי הסדר, ורק סעיפים שיש בהם תוכן:

- `## תכונות חדשות` (MINOR או MAJOR)
- `## תיקונים`
- `## נבדק ידנית` - מה נבדק עם בקר אמיתי, ואיך.
- `## דרישות` - אם השתנה משהו שהמשתמש צריך לדעת (למשל Python 3.10+ ב-PATH; ההתקנה לא כוללת את Python).

## לוח שחרור (dashboard)

לוח חי מקומי שמראה אחוזי התקדמות, זמן שנותר, מה קורה עכשיו, השלבים, יומן חי, משימות, משימות GitHub והבדיקות המקומיות. לוח לקריאה בלבד: הוא לא שולח ולא משחרר כלום.

- הפעלה (רץ עד שהגרסה מפורסמת, לכל היותר 3 שעות; נעילה מונעת עותק שני): `python tools/release_status/status_page.py`, ברקע.
- פתיחה: `tools/release_status/status.html` בדפדפן.
- עדכון: `python tools/release_status/log.py "מה עושים עכשיו"` בכל שלב. עדכון `tools/release_status/todo.json` (`[{"text": "...", "state": "todo|run|done"}]`) כשמשימה מתחילה או מסתיימת. `python tools/release_status/reset.py` מנקה את העמוד.
- בתחילת סשן בודקים שהלוח חי: הקובץ `tools/release_status/status-data.js` השתנה בדקה האחרונה.

## בדיקות מקומיות

`python tools/release_status/run_local_tests.py` מריץ את כל הסט: `test_io`, `test_features`, `test_logic`, `pe_test`. עם שמות - רק הם. בדיקה בודדת מוצגת בכרטיס משלה.

- הבדיקות רצות במקביל כברירת מחדל (אין בהן פורטים קבועים). `--serial` מריץ אחת אחרי השנייה.
- **עוצרים בכשל הראשון.** מריצים ברקע `python tools/release_status/watch_tests.py`: הוא מוחק תוצאה ישנה, מתחיל את ההרצה, ובכשל הראשון הורג את הריצה ויוצא עם 1. כשהכול עבר הוא מדפיס `FINISHED OK` ויוצא עם 0. מתקנים ומריצים הכול מחדש.
- בדיקה שנכשלה בהרצה המלאה רצה שוב לבד לפני שמכריזים עליה כשבורה.
- לא מפעילים הרצה נוספת בזמן שאחת רצה.
- בדיקה חדשה: קובץ חדש בתיקייה `tests/`. `npm test` מגלה אותו לבד, ויש להוסיף את שמו ל-`DEFAULT` ב-`tools/release_status/run_local_tests.py`.
- **הבדיקות רצות ב-Windows בלבד**: המנוע קורא ל-`ctypes.windll` בזמן הייבוא.

## נוהל

1. עדכון הלוח (`todo.json`, `log.py`).
2. איסוף התוכן: `git log v<הגרסה הקודמת>..HEAD --oneline` (אם אין עדיין תג קודם: `git log --oneline`). קביעת מספר הגרסה לפי הכללים למעלה.
3. הגדלת הגרסה: `npm version X.Y.Z --no-git-tag-version` (מעדכן `package.json` ו-`package-lock.json`). כתיבת קובץ הערות השחרור.
4. בדיקה ידנית עם בקר: לשאול את המשתמש לאשר שנעשתה, ולרשום אותה ב-`## נבדק ידנית`.
5. הרצת הבדיקות המקומיות עם השומר (ראה למעלה) עד `FINISHED OK`.
6. שמירה ושליחה: `git status` מציג רק את השינויים של השחרור, ואז `git add -A`, `git commit -m "Release vX.Y.Z"`, `git push origin main`. לוודא ש-`git status -sb` לא מציג "ahead".
7. לוודא שהתג לא קיים (התשובה חייבת להיות 404):

   ```
   TOKEN=$(printf 'protocol=https\nhost=github.com\n\n' | git credential fill | sed -n 's/^password=//p')
   curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $TOKEN" https://api.github.com/repos/giamat13/better-xbox-mode/git/ref/tags/vX.Y.Z
   ```

   הטוקן לא מודפס (`-o /dev/null`) ולא נשמר.
8. הפעלה:

   ```
   curl -s -o /dev/null -w "%{http_code}\n" -X POST -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json" https://api.github.com/repos/giamat13/better-xbox-mode/actions/workflows/release.yml/dispatches -d '{"ref":"main"}'
   ```

   תשובה 204 = הופעל. לא דוחפים תג ידנית: התהליך יוצר אותו בעצמו.
9. מעקב: `python tools/release_status/watch_release.py giamat13/better-xbox-mode release.yml` ברקע (מדפיס את המשימות, ויוצא עם 1 בכשל הראשון). בכשל: לקרוא את היומן של המשימה (`GET /repos/giamat13/better-xbox-mode/actions/jobs/<id>/logs`), לבטל את ההרצה (`POST /repos/giamat13/better-xbox-mode/actions/runs/<id>/cancel`), לתקן, לדחוף ולהפעיל שוב.
10. אחרי הצלחה: לבדוק שבשחרור יש בדיוק ארבעה קבצים: שני ה-exe, ה-`.exe.blockmap` וה-`latest.yml`. בלי `latest.yml` העדכון האוטומטי לא רואה את הגרסה החדשה, ולכן לא מסתפקים בבדיקה של שני ה-exe בלבד.
11. Issues: בכל issue שתוקן בגרסה, לכתוב "נכלל בגרסה vX.Y.Z" ולסגור אותו. רק issues שמופיעים בהודעות ה-commit (`Fixes #N`) או שהמשתמש ציין.
12. סיום הלוח: כל המשימות `done`, ושורת יומן אחרונה.

משך טיפוסי: הלוח מציג את הזמנים של השחרורים הקודמים.

## ההתקנה (installer) והגרסה הנייחת

- ההתקנה מתקינה לתיקיית המשתמש (`%LOCALAPPDATA%\Programs\Xbox Mode`), בלי הרשאות מנהל.
- ההתקנה מוסיפה את התוכנה להפעלה עם Windows (`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, הערך `Xbox Mode`). הסרת ההתקנה מוחקת את הערך. הגרסה הנייחת לא נרשמת להפעלה אוטומטית.
- הקבצים לא חתומים דיגיטלית: Windows SmartScreen עלול להציג אזהרה.
- בנייה מקומית: `npm run dist` יוצר את ארבעת קובצי השחרור ב-`dist/`.

## עדכון אוטומטי

- התוכנה המותקנת בודקת כל 6 שעות אם יש שחרור חדש ב-GitHub (דרך `latest.yml`). גרסה חדשה מורדת ברקע, ומותקנת כשהתוכנה נסגרת. המשתמש מקבל התראה על כך.
- רק ההתקנה מתעדכנת לבד. הקוד בודק שמסיר ההתקנה `Uninstall Xbox Mode.exe` נמצא לצד הקובץ. הגרסה הנייחת לא מתעדכנת: מורידים אותה ידנית.
- בפיתוח (`npm start`) אין עדכון אוטומטי.
- **בדיקה אחרי שחרור שני:** מתקינים את הגרסה הקודמת, מפרסמים גרסה חדשה, ובודקים שההתקנה מורידה אותה ומתעדכנת בסגירה הבאה. השחרור הראשון (1.0.0) לא ניתן לבדוק כך, כי אין לפניו גרסה מותקנת עם עדכון.

## בעיות נפוצות

| תסמין | פעולה |
|---|---|
| הלוח מראה "הכול נכשל" | `local-tests.json` ישן מהרצה שנהרגה: למחוק אותו |
| בדיקה נתקעת על פורט תפוס | תהליך או שרת נשאר: לסגור ולהריץ שוב |
| `git push` של תג נכשל | לא דוחפים תגים; מפעילים את התהליך |
| ה-API מחזיר 401 | `git credential fill` החזיר סיסמה ריקה: להתחבר מחדש ל-git |
| הלוח עצר בזמן | משימה ב-GitHub נכשלה; הלוח עוצר בכשל הראשון |
| `npm run dist` נכשל | לבדוק חיבור לאינטרנט (electron-builder מוריד כלים בבנייה הראשונה) |
