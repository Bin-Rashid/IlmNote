INSERT OR IGNORE INTO categories (name, slug, description, color) VALUES
('ইসলাম ও দ্বীন', 'islam', 'ইসলামিক জ্ঞান ও দ্বীনি বিষয়', '#176B4D'),
('ইতিহাস', 'history', 'ইতিহাস বিষয়ক লেখা', '#8B5A2B'),
('বিজ্ঞান', 'science', 'বিজ্ঞান ও গবেষণা', '#2563EB'),
('প্রযুক্তি', 'technology', 'প্রযুক্তি ও টেকনোলজি', '#7C3AED'),
('বই ও প্রবন্ধ', 'books', 'বই পর্যালোচনা ও প্রবন্ধ', '#D4AF37'),
('ব্যক্তিগত নোট', 'personal', 'ব্যক্তিগত নোট ও ডায়েরি', '#6B7280');

INSERT OR IGNORE INTO settings (key, value) VALUES
('site_name', 'IlmNote'),
('user_name', 'User'),
('theme', 'system'),
('font_family', 'Noto Sans Bengali'),
('font_size', '18'),
('line_height', '1.8'),
('view_mode', 'grid'),
('content_width', '760');