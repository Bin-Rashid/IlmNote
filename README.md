# IlmNote — Personal Learning & Knowledge Journal

বাংলা ভাষার জন্য অপ্টিমাইজড, স্থানীয়ভাবে চালিত ব্যক্তিগত জ্ঞানভান্ডার।

## ইনস্টল
1. Python 3.11+ ইনস্টল করুন (Add to PATH টিক দিন)।
2. `setup.bat` ডাবল-ক্লিক করুন।
3. `start.bat` ডাবল-ক্লিক করুন — ব্রাউজারে খুলে যাবে।

## ফন্ট যোগ করা
`static/fonts/` ফোল্ডারে `.ttf` রাখুন এবং `style.css`-এ `@font-face` যোগ করুন:

\`\`\`css
@font-face {
  font-family: 'Noto Sans Bengali';
  src: url('/static/fonts/NotoSansBengali-Regular.ttf');
}
\`\`\`

ফন্ট ডাউনলোড: https://fonts.google.com/noto/specimen/Noto+Sans+Bengali

## DB Browser for SQLite
1. https://sqlitebrowser.org/ থেকে ডাউনলোড করুন।
2. "Open Database" → `ilmnote.db` ফাইল নির্বাচন করুন।

## ব্যাকআপ
সেটিংস → ডাটাবেস ব্যাকআপ।

## ট্রাবলশুট
- Python পাওয়া যায়নি → PATH-এ Python যোগ করুন।
- পোর্ট 5000 ব্যস্ত → `app.py`-এ পোর্ট পরিবর্তন করুন।
- ফন্ট দেখাচ্ছে না → `.ttf` ফাইল static/fonts-এ আছে কিনা দেখুন।