// "We're down" page for UbyHost (brief 1163, disaster-recovery plan step 5).
// The owner routes this Worker for the domain during an outage; see
// docs/DISASTER_RECOVERY.md. It makes no outbound request and reads no data.

const PAGE = `<!doctype html>
<html lang="cs">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>UbyHost je dočasně nedostupný</title>
<style>
html { background: #fff; color: #1a1a1a; }
body { font-family: system-ui, sans-serif; line-height: 1.5; max-width: 36rem; margin: 0 auto; padding: 1.5rem 1rem; }
h1 { font-size: 1.5rem; margin: 0 0 1rem; }
h2 { font-size: 1.1rem; margin: 1.5rem 0 0.5rem; }
p { margin: 0 0 0.75rem; }
a { color: #0b4fa8; }
hr { border: 0; border-top: 1px solid #ccc; margin: 2rem 0; }
</style>
</head>
<body>
<main>
<h1>UbyHost je dočasně nedostupný</h1>
<p>Stěhujeme UbyHost na nový server. Služba se vrátí během několika hodin. Vaše data jsou v bezpečí.</p>
<h2>Pro ubytovatele</h2>
<p>Blíží-li se lhůta pro ohlášení hosta, ohlaste ho ručně v portálu policie (<a href="https://ubyport.policie.cz/">Ubyport</a>) jako obvykle.</p>
<h2>Pro hosty</h2>
<p>Nemusíte nic dělat. Pokud bude něco potřeba, ubytovatel se vám ozve.</p>
<hr>
<section lang="en">
<h1>UbyHost is temporarily unavailable</h1>
<p>We are moving UbyHost to a new server. It will be back within hours. Your data is safe.</p>
<h2>For hosts</h2>
<p>If a guest's registration deadline is near, register the guest by hand in the police portal (<a href="https://ubyport.policie.cz/">Ubyport</a>) as usual.</p>
<h2>For guests</h2>
<p>There is nothing for you to do. Your host will contact you if needed.</p>
</section>
</main>
</body>
</html>
`;

const HEADERS = {
  "content-type": "text/html; charset=utf-8",
  "cache-control": "no-store",
  "retry-after": "3600",
  "x-robots-tag": "noindex",
};

export default {
  async fetch(request) {
    const body = request.method === "HEAD" ? null : PAGE;
    return new Response(body, { status: 503, headers: HEADERS });
  },
};
