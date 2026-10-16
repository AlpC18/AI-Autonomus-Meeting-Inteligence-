// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

/** Turkish text of the interface, keyed by the English original. */
export const TR: Readonly<Record<string, string>> = {
  // Shell and navigation
  "Could not reach the desktop backend: {error}": "Masaüstü arka ucuna ulaşılamadı: {error}",
  Views: "Görünümler",
  "Get started": "Başlarken",
  "Live meeting": "Canlı toplantı",
  "Past meetings": "Geçmiş toplantılar",
  Settings: "Ayarlar",
  "Continuum {version} is available.": "Continuum {version} hazır.",
  "Installing…": "Yükleniyor…",
  "Install and restart": "Yükle ve yeniden başlat",
  "The update failed: {error}": "Güncelleme başarısız oldu: {error}",

  // Live meeting
  "Live transcript": "Canlı döküm",
  "Connecting to the engine…": "Motora bağlanılıyor…",
  Listening: "Dinleniyor",
  "Engine not running. Retrying…": "Motor çalışmıyor. Yeniden deneniyor…",
  "Current meeting": "Mevcut toplantı",
  "Ending…": "Bitiriliyor…",
  "End meeting": "Toplantıyı bitir",
  "Brief me": "Özet çıkar",
  "Project: {project}": "Proje: {project}",
  "Switch project": "Projeyi değiştir",
  "another project": "başka bir proje",
  Switch: "Değiştir",
  "Company documents in memory are used by fact checks and answers.":
    "Bellekteki şirket belgeleri doğruluk kontrollerinde ve yanıtlarda kullanılır.",
  "Add documents…": "Belge ekle…",
  "Add documents to this project's memory": "Bu projenin belleğine belge ekle",
  Documents: "Belgeler",
  "Document import": "Belge aktarımı",
  "Added {name} ({count} passages)": "{name} eklendi ({count} bölüm)",
  "Not added: {error}": "Eklenmedi: {error}",
  "Could not switch project: {error}": "Proje değiştirilemedi: {error}",
  "Brief from earlier meetings": "Önceki toplantılardan özet",
  "From earlier meetings": "Önceki toplantılardan",
  "Action items so far": "Şu ana kadarki yapılacaklar",
  "due {date}": "son tarih {date}",
  "The summary could not be made: {error}": "Özet çıkarılamadı: {error}",
  "{count} proposed action(s) are waiting for your approval below.": "{count} önerilen eylem aşağıda onayınızı bekliyor.",
  "Not proposed: {error}": "Önerilmedi: {error}",
  "Hints from the last meeting": "Son toplantıdan ipuçları",
  "Talk time in the last meeting": "Son toplantıdaki konuşma süreleri",
  Speaker: "Konuşan",
  "Talk time": "Konuşma süresi",
  "Longest turn": "En uzun konuşma",
  Interruptions: "Söz kesme",

  // Speaker names
  "Type a name.": "Bir ad yazın.",
  "Use at most {count} characters.": "En fazla {count} karakter kullanın.",
  "Leave out * ` _ [ ] < > | # and \\.": "* ` _ [ ] < > | # ve \\ karakterlerini kullanmayın.",
  '"{name}" is reserved.': '"{name}" ayrılmış bir addır.',
  "{from} will be shown as {to}.": "{from} artık {to} olarak gösterilecek.",
  "The engine is not connected; try again in a moment.": "Motor bağlı değil; birazdan tekrar deneyin.",
  "Name a speaker": "Konuşana ad ver",
  "Real name": "Gerçek ad",
  "e.g. Ana": "ör. Ayşe",
  Rename: "Yeniden adlandır",

  // Notes
  "The engine is not connected; your note was kept here and not added yet.":
    "Motor bağlı değil; notunuz burada saklandı, henüz eklenmedi.",
  Notes: "Notlar",
  "Write what matters to you. It is added to the transcript at this moment.":
    "Sizin için önemli olanı yazın. Dökümde tam bu ana eklenir.",
  "e.g. Push back on the December date": "ör. Aralık tarihine itiraz et",
  "Add note": "Not ekle",
  "Waiting for the engine…": "Motor bekleniyor…",

  // Ask
  "Ask your meetings": "Toplantılarınıza sorun",
  Question: "Soru",
  "e.g. What did we decide about the budget?": "ör. Bütçe hakkında ne karar verdik?",
  Ask: "Sor",
  "Looking through your meetings…": "Toplantılarınıza bakılıyor…",
  disputed: "itiraz edildi",

  // Overlay
  earlier: "daha önce",
  "Fact check": "Doğruluk kontrolü",
  "Dismiss fact check": "Doğruluk kontrolünü kapat",
  "Said now": "Şimdi söylenen",
  "On record": "Kayıtlarda",
  "Code context": "Kod bağlamı",
  "Commitment risk": "Taahhüt riski",
  Hesitation: "Tereddüt",
  "Dismiss {what}": "Kapat: {what}",

  // Proposed actions
  "GitHub issue in {repo}": "{repo} deposunda GitHub kaydı",
  "Labels: {labels}": "Etiketler: {labels}",
  "Approve and create": "Onayla ve oluştur",
  "GitLab issue in {project}": "{project} projesinde GitLab kaydı",
  "Jira task in project {project}": "{project} projesinde Jira görevi",
  "Slack message to your configured channel": "Ayarladığınız kanala Slack mesajı",
  "Approve and send": "Onayla ve gönder",
  "Google Calendar deadline": "Google Takvim son tarihi",
  "Due: {date} (all day)": "Son tarih: {date} (tüm gün)",
  "Approve and schedule": "Onayla ve takvime ekle",
  "E-mail from your Gmail": "Gmail hesabınızdan e-posta",
  "To: {to}": "Alıcı: {to}",
  "Notion page under your configured parent page": "Ayarladığınız üst sayfanın altında Notion sayfası",
  "Decision recorded.": "Karar kaydedildi.",
  "Done: {result}": "Tamamlandı: {result}",
  "Rejected. Nothing was sent.": "Reddedildi. Hiçbir şey gönderilmedi.",
  "Failed: {result}": "Başarısız: {result}",
  "no details given": "ayrıntı verilmedi",
  "Could not load proposed actions: {error}": "Önerilen eylemler yüklenemedi: {error}",
  "Could not complete that: {error}": "Bu işlem tamamlanamadı: {error}",
  "Proposed actions": "Önerilen eylemler",
  "Nothing is waiting for you.": "Bekleyen bir şey yok.",
  Reject: "Reddet",
  "Working…": "Çalışıyor…",

  // Past meetings
  "That meeting could not be read.": "Bu toplantı okunamadı.",
  "The recording could not be played.": "Kayıt oynatılamadı.",
  "Summarizing… the transcript is being sent to your configured AI provider.":
    "Özetleniyor… döküm ayarladığınız yapay zekâ sağlayıcısına gönderiliyor.",
  "Summary saved in the notes.": "Özet notlara kaydedildi.",
  "Search all meetings": "Tüm toplantılarda ara",
  Search: "Ara",
  "Search results": "Arama sonuçları",
  "No lines match.": "Eşleşen satır yok.",
  Meetings: "Toplantılar",
  "No meeting notes yet.": "Henüz toplantı notu yok.",
  summarized: "özetlendi",
  "Choose a meeting to read it.": "Okumak için bir toplantı seçin.",
  "No recording is linked to this meeting.": "Bu toplantıya bağlı kayıt yok.",
  "Filter this meeting": "Bu toplantıyı filtrele",
  "Filter lines": "Satırları filtrele",
  "Summarizing…": "Özetleniyor…",
  "Summarize again": "Yeniden özetle",
  "Summarize with AI": "Yapay zekâ ile özetle",
  "Play from {time}": "{time} anından oynat",

  // Settings screen
  "Saving and restarting the engine…": "Kaydediliyor ve motor yeniden başlatılıyor…",
  "Saved. The engine restarted with the new settings.": "Kaydedildi. Motor yeni ayarlarla yeniden başladı.",
  "Finish signing in to Google in your browser…": "Google girişini tarayıcınızda tamamlayın…",
  "Testing the saved connections…": "Kayıtlı bağlantılar test ediliyor…",
  "Loading settings…": "Ayarlar yükleniyor…",
  "Saved in Keychain — type to replace": "Anahtar Zinciri'nde kayıtlı — değiştirmek için yazın",
  "Not set": "Ayarlanmadı",
  Remove: "Kaldır",
  None: "Yok",
  "Save the Google client ID and secret first.": "Önce Google istemci kimliğini ve gizli anahtarını kaydedin.",
  "Connect Google…": "Google'ı bağla…",
  "Save and restart engine": "Kaydet ve motoru yeniden başlat",
  "Signs in to each saved integration and asks the AI provider for a one-word reply.":
    "Kayıtlı her entegrasyona giriş yapar ve yapay zekâ sağlayıcısından tek kelimelik bir yanıt ister.",
  "Test connections": "Bağlantıları test et",

  // First-run checklist
  "Saving…": "Kaydediliyor…",
  "(choose)": "(seçin)",
  saved: "kayıtlı",
  "Choose the notes folder": "Not klasörünü seçin",
  "Choose…": "Seç…",
  Save: "Kaydet",
  Done: "Tamam",
  "To do": "Yapılacak",
  "Open {name} settings": "{name} ayarlarını aç",
  "All settings": "Tüm ayarlar",
  "Hide this checklist": "Bu listeyi gizle",
  Microphone: "Mikrofon",
  "Screen Recording": "Ekran Kaydı",
  "Let Continuum hear the meeting": "Continuum'un toplantıyı duymasına izin verin",
  "macOS asks for Microphone and Screen Recording (for the other people's audio). Allow both, then say something: this step is done when your words appear in the Live view.":
    "macOS, Mikrofon ve Ekran Kaydı (diğer kişilerin sesi için) izni ister. İkisine de izin verin ve bir şey söyleyin: sözleriniz Canlı görünümde belirince bu adım tamamlanır.",
  "Choose an AI provider": "Bir yapay zekâ sağlayıcısı seçin",
  "Used for summaries, answers and briefs. Groq and Gemini have free keys; Ollama runs on this computer with no key.":
    "Özetler, yanıtlar ve brifingler için kullanılır. Groq ve Gemini ücretsiz anahtar verir; Ollama bu bilgisayarda anahtarsız çalışır.",
  "Name your workspace and project": "Çalışma alanınızı ve projenizi adlandırın",
  "Meetings are remembered per workspace and project, so you can ask about them later.":
    "Toplantılar çalışma alanı ve proje bazında hatırlanır; böylece sonradan onlar hakkında soru sorabilirsiniz.",
  "Pick a notes folder": "Bir not klasörü seçin",
  "Each meeting is also saved there as a Markdown file (an Obsidian vault folder works well).":
    "Her toplantı oraya Markdown dosyası olarak da kaydedilir (bir Obsidian kasası klasörü iyi çalışır).",
  "Tell speakers apart (optional)": "Konuşanları ayırt et (isteğe bağlı)",
  "A free Hugging Face token lets Continuum separate and recognise the other people in a call.":
    "Ücretsiz bir Hugging Face anahtarı, Continuum'un görüşmedeki diğer kişileri ayırıp tanımasını sağlar.",

  // Settings fields: groups
  Privacy: "Gizlilik",
  AI: "Yapay zekâ",
  Actions: "Eylemler",

  // Settings fields: labels and help
  Language: "Dil",
  "en: English, tr: Türkçe. The app, notes, hints and AI summaries use it; people are transcribed in whatever language they speak.":
    "en: English, tr: Türkçe. Uygulama, notlar, ipuçları ve yapay zekâ özetleri bu dili kullanır; konuşmalar hangi dilde yapılırsa o dilde dökülür.",
  "Notes folder": "Not klasörü",
  "Each meeting is saved here as Markdown (e.g. a folder in your Obsidian vault).":
    "Her toplantı buraya Markdown olarak kaydedilir (ör. Obsidian kasanızdaki bir klasör).",
  Workspace: "Çalışma alanı",
  "Memory and notes are kept per workspace and project. Letters, digits, '_', '.', '-'.":
    "Bellek ve notlar çalışma alanı ve proje bazında tutulur. Harf, rakam, '_', '.', '-'.",
  Project: "Proje",
  "Set both workspace and project to keep a searchable memory.":
    "Aranabilir bir bellek için çalışma alanını ve projeyi birlikte ayarlayın.",
  "Code folders": "Kod klasörleri",
  "Comma-separated local checkouts. When a meeting names something in the code, the overlay lists the files. Nothing leaves this machine.":
    "Virgülle ayrılmış yerel kod klasörleri. Toplantıda koddan bir şey geçtiğinde katman ilgili dosyaları listeler. Hiçbir şey bu bilgisayardan çıkmaz.",
  "Listen to": "Dinlenecek kaynaklar",
  "Your microphone, the other participants (system audio), or both.":
    "Mikrofonunuz, diğer katılımcılar (sistem sesi) ya da ikisi birden.",
  "Hear only meeting apps": "Yalnızca toplantı uygulamalarını dinle",
  "Other participants are heard only from Zoom, Teams, Slack, Webex, FaceTime, Meet in a browser and similar apps, so music and videos stay out. macOS, Windows 10 (2004) or later, and Linux with PulseAudio or PipeWire.":
    "Diğer katılımcılar yalnızca Zoom, Teams, Slack, Webex, FaceTime, tarayıcıda Meet ve benzeri uygulamalardan duyulur; müzik ve videolar dışarıda kalır. macOS, Windows 10 (2004) veya üstü ve PulseAudio ya da PipeWire kullanan Linux.",
  "More meeting apps": "Diğer toplantı uygulamaları",
  "Bundle IDs of other meeting apps to hear, comma-separated (find one with: osascript -e 'id of app \"AppName\"').":
    "Dinlenecek diğer toplantı uygulamalarının paket kimlikleri, virgülle ayrılmış (bulmak için: osascript -e 'id of app \"UygulamaAdı\"').",
  "Calls in the browser from the extension": "Tarayıcıdaki görüşmeler eklentiden",
  "Install the Continuum browser extension (apps/browser-extension) in Chrome, Edge, Brave or Arc and click it on the meeting tab: only that tab is heard, never your other tabs. Browsers are then left out of system audio (macOS).":
    "Continuum tarayıcı eklentisini (apps/browser-extension) Chrome, Edge, Brave veya Arc'a kurun ve toplantı sekmesinde tıklayın: yalnızca o sekme duyulur, diğer sekmeleriniz asla. Tarayıcılar böylece sistem sesinin dışında kalır (macOS).",
  "Extension ID": "Eklenti kimliği",
  "Optional: the ID chrome://extensions shows for the Continuum extension, so no other extension can send audio.":
    "İsteğe bağlı: chrome://extensions sayfasında Continuum eklentisi için görünen kimlik; böylece başka hiçbir eklenti ses gönderemez.",
  "Speech model": "Konuşma modeli",
  "Larger is more accurate and slower.": "Büyük model daha doğru ama daha yavaştır.",
  "Speech engine": "Konuşma motoru",
  "auto uses the Apple Silicon GPU when available.": "auto, varsa Apple Silicon GPU'yu kullanır.",
  "Hugging Face token": "Hugging Face anahtarı",
  "Enables telling speakers apart (pyannote).": "Konuşanları ayırt etmeyi sağlar (pyannote).",
  "Recognise people you named": "Adlandırdığınız kişileri tanı",
  "Keeps the voices of speakers you name (on this computer only), so later meetings show their names.":
    "Adlandırdığınız konuşanların seslerini (yalnızca bu bilgisayarda) saklar; sonraki toplantılarda adları görünür.",
  "Hide personal data in saved notes": "Kaydedilen notlarda kişisel verileri gizle",
  "E-mails, phone and card numbers, IBANs, keys and passwords are replaced before saving.":
    "E-postalar, telefon ve kart numaraları, IBAN'lar, anahtarlar ve parolalar kaydetmeden önce gizlenir.",
  "Forget memories after (days)": "Belleği şu kadar gün sonra unut",
  "Empty keeps everything.": "Boş bırakılırsa her şey saklanır.",
  "Require disk encryption": "Disk şifrelemesi zorunlu olsun",
  "Store nothing unless FileVault is on. The live transcript still works.":
    "FileVault açık değilse hiçbir şey saklanmaz. Canlı döküm yine çalışır.",
  "Start when a call begins": "Görüşme başlayınca başla",
  "Listen only while another app (Zoom, Meet, Teams, ...) uses the microphone.":
    "Yalnızca başka bir uygulama (Zoom, Meet, Teams, ...) mikrofonu kullanırken dinle.",
  "End a meeting after silence (minutes)": "Sessizlikten sonra toplantıyı bitir (dakika)",
  "The meeting is summarised and a new one starts. Empty never ends it automatically.":
    "Toplantı özetlenir ve yenisi başlar. Boş bırakılırsa otomatik olarak bitmez.",
  "Record meeting audio": "Toplantı sesini kaydet",
  "Saves the audio next to the notes for playback. Recordings are not redacted.":
    "Sesi tekrar dinlemek için notların yanına kaydeder. Kayıtlarda kişisel veriler gizlenmez.",
  "AI provider": "Yapay zekâ sağlayıcısı",
  "Free: groq, gemini, openrouter, mistral. Local: ollama, lmstudio. Transcripts are sent to the provider you pick.":
    "Ücretsiz: groq, gemini, openrouter, mistral. Yerel: ollama, lmstudio. Dökümler seçtiğiniz sağlayıcıya gönderilir.",
  "AI model": "Yapay zekâ modeli",
  "Empty uses the provider's default (required for openrouter, lmstudio and custom).":
    "Boş bırakılırsa sağlayıcının varsayılanı kullanılır (openrouter, lmstudio ve custom için gereklidir).",
  "AI server URL": "Yapay zekâ sunucu adresi",
  "Only for custom, OpenAI-compatible servers.": "Yalnızca OpenAI uyumlu özel sunucular için.",
  "AI API key": "Yapay zekâ API anahtarı",
  "Not needed for ollama or lmstudio.": "ollama veya lmstudio için gerekmez.",
  "AI hesitation finder": "Yapay zekâ tereddüt bulucu",
  "When a meeting ends, also list doubts the phrase list missed. Sends the transcript to your AI provider.":
    "Toplantı bitince ifade listesinin kaçırdığı tereddütleri de listeler. Dökümü yapay zekâ sağlayıcınıza gönderir.",
  "AI fact check": "Yapay zekâ doğruluk kontrolü",
  "Also catch contradictions without numbers. Sends statements to your AI provider.":
    "Sayı içermeyen çelişkileri de yakalar. İfadeleri yapay zekâ sağlayıcınıza gönderir.",
  "Live action items": "Canlı yapılacaklar",
  "Show tasks as they are said. Sends the transcript to your AI provider at most every 3 minutes.":
    "Görevleri söylendikçe gösterir. Dökümü yapay zekâ sağlayıcınıza en fazla 3 dakikada bir gönderir.",
  "Commitments and hesitations": "Taahhütler ve tereddütler",
  "Lists promised dates and moments of doubt in the notes. Runs on this computer.":
    "Verilen tarihleri ve tereddüt anlarını notlarda listeler. Bu bilgisayarda çalışır.",
  "Check promised dates against Jira, GitHub and GitLab": "Verilen tarihleri Jira, GitHub ve GitLab ile karşılaştır",
  "Warns when someone promises a date while holding many open Jira, GitHub or GitLab issues, or a full sprint. Sends their name to those services.":
    "Birisi çok sayıda açık Jira, GitHub veya GitLab işi ya da dolu bir sprint varken tarih verirse uyarır. Kişinin adını bu servislere gönderir.",
  "Propose after each meeting": "Her toplantıdan sonra öner",
  "Comma-separated: calendar, slack, email (recap to the calendar attendees), notion, jira:PROJECT, github:owner/name, gitlab:group/name. Each still needs your approval.":
    "Virgülle ayrılmış: calendar, slack, email (takvim katılımcılarına özet), notion, jira:PROJE, github:sahip/ad, gitlab:grup/ad. Her biri yine de onayınızı gerektirir.",
  "GitHub repositories": "GitHub depoları",
  "Comma-separated owner/name; issues can only be proposed for these.": "Virgülle ayrılmış sahip/ad; kayıtlar yalnızca bunlar için önerilebilir.",
  "GitHub token": "GitHub anahtarı",
  "Fine-grained token with Issues: read and write.": "Issues için okuma ve yazma izni olan ayrıntılı anahtar.",
  "GitLab projects": "GitLab projeleri",
  "Comma-separated group/name; issues can only be proposed for these.": "Virgülle ayrılmış grup/ad; kayıtlar yalnızca bunlar için önerilebilir.",
  "GitLab address": "GitLab adresi",
  "Leave empty for gitlab.com; https://… for a self-managed GitLab.": "gitlab.com için boş bırakın; kendi GitLab sunucunuz için https://…",
  "GitLab token": "GitLab anahtarı",
  "Personal or project access token with the api scope.": "api kapsamına sahip kişisel veya proje erişim anahtarı.",
  "Slack webhook URL": "Slack webhook adresi",
  "Incoming-webhook URL of the one channel messages may go to.": "Mesajların gidebileceği tek kanalın gelen webhook adresi.",
  "Jira site": "Jira sitesi",
  "Jira account e-mail": "Jira hesap e-postası",
  "Jira API token": "Jira API anahtarı",
  "From id.atlassian.com > Security > API tokens.": "id.atlassian.com > Security > API tokens bölümünden.",
  "Jira projects": "Jira projeleri",
  "Comma-separated project keys, e.g. WEB,OPS.": "Virgülle ayrılmış proje anahtarları, ör. WEB,OPS.",
  "Notion integration token": "Notion entegrasyon anahtarı",
  "From notion.so/profile/integrations. Share the parent page with the integration.":
    "notion.so/profile/integrations adresinden. Üst sayfayı entegrasyonla paylaşın.",
  "Notion parent page": "Notion üst sayfası",
  "Link or id of the page meeting summaries go under.": "Toplantı özetlerinin altına ekleneceği sayfanın bağlantısı veya kimliği.",
  "Google client ID": "Google istemci kimliği",
  "For calendar, meeting titles and recap e-mails: an OAuth client of type 'Desktop app' in Google Cloud.":
    "Takvim, toplantı başlıkları ve özet e-postaları için: Google Cloud'da 'Desktop app' türünde bir OAuth istemcisi.",
  "Google client secret": "Google gizli anahtarı",
  "Google refresh token": "Google yenileme anahtarı",
  "Save the client ID and secret, then use Connect Google to fill this in.":
    "İstemci kimliğini ve gizli anahtarı kaydedin, ardından bunu doldurmak için Google'ı bağla'yı kullanın.",
  "Google calendar": "Google takvimi",
  "Empty uses your primary calendar.": "Boş bırakılırsa birincil takviminiz kullanılır.",
  Translation: "Çeviri",
  "Copy follow-up email": "Toplantı sonrası e-postayı kopyala",
  "Open in mail app": "E-posta uygulamasında aç",
  "Copied.": "Kopyalandı.",
  "Could not copy; use Open in mail app.": "Kopyalanamadı; E-posta uygulamasında aç'ı kullanın.",
  "No mail app answered.": "Hiçbir e-posta uygulaması yanıt vermedi.",
  "Copy diagnostics": "Tanılama bilgilerini kopyala",
  Diagnostics: "Tanılama bilgileri",
  "Versions, settings without secrets, problems and recent engine log lines, for a bug report.":
    "Hata bildirimi için sürümler, gizli bilgiler olmadan ayarlar, sorunlar ve son motor günlüğü satırları.",
  "Diagnostics copied. Paste them into your bug report; secrets and personal data are left out.":
    "Tanılama bilgileri kopyalandı. Hata bildiriminize yapıştırın; gizli bilgiler ve kişisel veriler dahil değildir.",
  "Copy the diagnostics below into your bug report.": "Aşağıdaki tanılama bilgilerini hata bildiriminize kopyalayın.",
  "Fact-check shared slides": "Paylaşılan slaytları doğrula",
  "Every 10 s, reads the meeting window (never other windows) with on-device text recognition and checks the figures on shared slides against memory. macOS; needs Screen Recording.":
    "10 saniyede bir toplantı penceresini (asla başka pencereleri değil) cihaz üzerindeki metin tanıma ile okur ve paylaşılan slaytlardaki rakamları bellekle karşılaştırır. macOS; Ekran Kaydı izni gerekir.",
  "Live translation": "Canlı çeviri",
  "Shows each line translated into this language under the transcript. Sends every line to your AI provider.":
    "Her satırın bu dile çevirisini dökümün altında gösterir. Her satırı yapay zekâ sağlayıcınıza gönderir.",
};
