package guest

import (
	"strings"

	"github.com/jsfpechar-ops/jsfpecharoperations/go/internal/validation"
)

// passportRequired is reporting.guest_needs_passport_photo.
// enteredBy and identityVerifiedAt come from the stored row, or "guest" and ""
// for a new guest (guest.py:2486 passes exactly that stub).
func passportRequired(policy, nationality, enteredBy, identityVerifiedAt string) bool {
	if strings.ToLower(strings.TrimSpace(policy)) != "required_foreign" {
		return false
	}
	if !validation.GuestIsReportable(nationality) {
		return false
	}
	if enteredBy == "host" { // empty counts as "guest"
		return false
	}
	// guest_identity_verified: non-reportable is always verified (excluded above);
	// otherwise verified only when identity_verified_at is set.
	return identityVerifiedAt == ""
}

// passportUploadMessages is guest.PASSPORT_UPLOAD_MESSAGES, keyed by the English
// refusal from passportphotos.Prepare. English and unknown languages fall back to it.
var passportUploadMessages = map[string]map[string]string{
	"cs": {
		"Upload a JPEG, PNG, or WebP photo of your passport ID page, or a PDF (for example a registration form with up to 11 guests).": "Nahrajte fotografii pasu (JPEG, PNG, WebP) nebo PDF (např. registrační formulář až pro 11 hostů).",
		"The uploaded file looks empty.":                                             "Nahraný soubor vypadá prázdně.",
		"The PDF is too large. Use a file under 15 MB.":                              "PDF je příliš velké. Maximálně 15 MB.",
		"The file does not look like a valid PDF.":                                   "Soubor nevypadá jako platné PDF.",
		"The photo is too large. Use a file under 5 MB.":                             "Fotografie je příliš velká. Maximálně 5 MB.",
		"The file does not look like a valid image.":                                 "Soubor nevypadá jako platný obrázek.",
		"The photo has too many pixels. Take it again at the normal camera setting.": "Fotografie má příliš mnoho pixelů. Vyfoťte ji znovu v běžném nastavení fotoaparátu.",
	},
	"de": {
		"Upload a JPEG, PNG, or WebP photo of your passport ID page, or a PDF (for example a registration form with up to 11 guests).": "Laden Sie ein JPEG-, PNG- oder WebP-Foto Ihrer Reisepass-Datenseite oder ein PDF hoch (zum Beispiel ein Meldeformular mit bis zu 11 Gästen).",
		"The uploaded file looks empty.":                                             "Die hochgeladene Datei scheint leer zu sein.",
		"The PDF is too large. Use a file under 15 MB.":                              "Das PDF ist zu groß. Verwenden Sie eine Datei unter 15 MB.",
		"The file does not look like a valid PDF.":                                   "Die Datei scheint kein gültiges PDF zu sein.",
		"The photo is too large. Use a file under 5 MB.":                             "Das Foto ist zu groß. Verwenden Sie eine Datei unter 5 MB.",
		"The file does not look like a valid image.":                                 "Die Datei scheint kein gültiges Bild zu sein.",
		"The photo has too many pixels. Take it again at the normal camera setting.": "Das Foto hat zu viele Pixel. Nehmen Sie es mit der normalen Kameraeinstellung erneut auf.",
	},
	"es": {
		"Upload a JPEG, PNG, or WebP photo of your passport ID page, or a PDF (for example a registration form with up to 11 guests).": "Suba una foto JPEG, PNG o WebP de la página de datos de su pasaporte, o un PDF (por ejemplo, un formulario de registro de hasta 11 huéspedes).",
		"The uploaded file looks empty.":                                             "El archivo subido parece estar vacío.",
		"The PDF is too large. Use a file under 15 MB.":                              "El PDF es demasiado grande. Use un archivo de menos de 15 MB.",
		"The file does not look like a valid PDF.":                                   "El archivo no parece un PDF válido.",
		"The photo is too large. Use a file under 5 MB.":                             "La foto es demasiado grande. Use un archivo de menos de 5 MB.",
		"The file does not look like a valid image.":                                 "El archivo no parece una imagen válida.",
		"The photo has too many pixels. Take it again at the normal camera setting.": "La foto tiene demasiados píxeles. Vuelva a hacerla con la configuración normal de la cámara.",
	},
	"fr": {
		"Upload a JPEG, PNG, or WebP photo of your passport ID page, or a PDF (for example a registration form with up to 11 guests).": "Téléversez une photo JPEG, PNG ou WebP de la page d'identité de votre passeport, ou un PDF (par exemple un formulaire d'enregistrement de 11 voyageurs maximum).",
		"The uploaded file looks empty.":                                             "Le fichier téléversé semble vide.",
		"The PDF is too large. Use a file under 15 MB.":                              "Le PDF est trop volumineux. Utilisez un fichier de moins de 15 Mo.",
		"The file does not look like a valid PDF.":                                   "Le fichier ne semble pas être un PDF valide.",
		"The photo is too large. Use a file under 5 MB.":                             "La photo est trop volumineuse. Utilisez un fichier de moins de 5 Mo.",
		"The file does not look like a valid image.":                                 "Le fichier ne semble pas être une image valide.",
		"The photo has too many pixels. Take it again at the normal camera setting.": "La photo comporte trop de pixels. Reprenez-la avec le réglage normal de l'appareil photo.",
	},
	"uk": {
		"Upload a JPEG, PNG, or WebP photo of your passport ID page, or a PDF (for example a registration form with up to 11 guests).": "Завантажте фото сторінки паспорта з особистими даними у форматі JPEG, PNG або WebP чи PDF (наприклад, реєстраційну форму на 11 гостей максимум).",
		"The uploaded file looks empty.":                                             "Завантажений файл, схоже, порожній.",
		"The PDF is too large. Use a file under 15 MB.":                              "PDF завеликий. Використайте файл до 15 МБ.",
		"The file does not look like a valid PDF.":                                   "Файл не схожий на дійсний PDF.",
		"The photo is too large. Use a file under 5 MB.":                             "Фото завелике. Використайте файл до 5 МБ.",
		"The file does not look like a valid image.":                                 "Файл не схожий на дійсне зображення.",
		"The photo has too many pixels. Take it again at the normal camera setting.": "Фото має забагато пікселів. Сфотографуйте ще раз зі звичайними налаштуваннями камери.",
	},
}

// passportUploadText returns the localized refusal for a Prepare error, as
// PASSPORT_UPLOAD_MESSAGES.get(lang, {}).get(msg, msg) does.
func passportUploadText(lang, msg string) string {
	if t, ok := passportUploadMessages[lang][msg]; ok {
		return t
	}
	return msg
}

// guestDataDir is the data directory the host read path uses (stays privacyDataDir).
func guestDataDir(getenv func(string) string) string {
	if d := strings.TrimSpace(getenv("UBYHOST_DATA_DIR")); d != "" {
		return d
	}
	return "data"
}
