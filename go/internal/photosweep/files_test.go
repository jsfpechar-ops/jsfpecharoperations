package photosweep

import (
	"os"
	"path/filepath"
	"testing"
)

func TestPyIntMatchesPythonInt(t *testing.T) {
	ok := map[string]string{"1001": "1001", "02002": "2002", "+2003": "2003", "-5": "-5",
		"1_002": "1002", " 7 ": "7", "\x1c8": "8", "\u0663\u0664": "34", "99999999999999999999": "99999999999999999999"}
	for in, want := range ok {
		n, good := pyInt(in)
		if !good || n.String() != want {
			t.Errorf("pyInt(%q) = %v, %v; want %s", in, n, good, want)
		}
	}
	for _, in := range []string{"", "abc", "2006_", "_1", "1__0", "+", "+_5", "1.5", "0x10", "1 0"} {
		if _, good := pyInt(in); good {
			t.Errorf("pyInt(%q) accepted; Python raises ValueError", in)
		}
	}
}

func TestPySuffixAndStem(t *testing.T) {
	cases := [][3]string{{"1001.jpg", ".jpg", "1001"}, {".jpg", "", ".jpg"}, {"x.", "", "x."},
		{"a.tar.jpg", ".jpg", "a.tar"}, {"noext", "", "noext"}, {"..jpg", ".jpg", "."}}
	for _, c := range cases {
		if got := pySuffix(c[0]); got != c[1] {
			t.Errorf("pySuffix(%q) = %q, want %q", c[0], got, c[1])
		}
		if got := pyStem(c[0]); got != c[2] {
			t.Errorf("pyStem(%q) = %q, want %q", c[0], got, c[2])
		}
	}
}

func TestPyJSONStringEnsureASCII(t *testing.T) {
	cases := map[string]string{"check-in on or before 2026-11-06": `"check-in on or before 2026-11-06"`,
		"a\"b\\c\n\x01": `"a\"b\\c\n\u0001"`, "\u00e9\u20ac": `"\u00e9\u20ac"`, "\U0001F600": `"\ud83d\ude00"`, "\x7f": `"\u007f"`}
	for in, want := range cases {
		if got := pyJSONString(in); got != want {
			t.Errorf("pyJSONString(%q) = %s, want %s", in, got, want)
		}
	}
}

func TestDeletePhotoRemovesCanonicalNamesOnly(t *testing.T) {
	dir := t.TempDir()
	for _, name := range []string{"5.jpg.enc", "5.pdf", "5.JPG", "05.png"} {
		if err := os.WriteFile(filepath.Join(dir, name), []byte("x"), 0o600); err != nil {
			t.Fatal(err)
		}
	}
	if has, err := hasPhoto(dir, "5"); err != nil || !has {
		t.Fatalf("hasPhoto = %v, %v", has, err)
	}
	if err := deletePhoto(dir, "5"); err != nil {
		t.Fatal(err)
	}
	for name, want := range map[string]bool{"5.jpg.enc": false, "5.pdf": false, "5.JPG": true, "05.png": true} {
		_, err := os.Lstat(filepath.Join(dir, name))
		if (err == nil) != want {
			t.Errorf("%s exists = %v, want %v", name, err == nil, want)
		}
	}
}

func TestRemoveFileFailsOnUnwritableDir(t *testing.T) {
	if os.Geteuid() == 0 {
		t.Skip("root ignores directory permissions")
	}
	dir := t.TempDir()
	path := filepath.Join(dir, "1.jpg")
	if err := os.WriteFile(path, []byte("x"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.Chmod(dir, 0o555); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = os.Chmod(dir, 0o755) })
	if err := removeFile(path); err == nil {
		t.Fatal("removeFile in a read-only directory returned nil")
	}
	if err := removeFile(filepath.Join(dir, "gone.jpg")); err != nil {
		t.Fatalf("a missing file must not fail: %v", err)
	}
}
