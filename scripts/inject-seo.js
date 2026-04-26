const fs = require("fs");
const path = require("path");

const config = JSON.parse(
  fs.readFileSync(path.join(__dirname, "../sites/email-tools/config.json"), "utf-8")
);

const htmlPath = path.join(__dirname, "../dist/email-tools/index.html");
let html = fs.readFileSync(htmlPath, "utf-8");

const seoTags = `
<meta name="google-site-verification" content="${config.gsc_verification}" />
<link rel="canonical" href="${config.base_url}" />
<meta name="description" content="${config.site_description}" />
<meta property="og:title" content="${config.site_name}" />
<meta property="og:description" content="${config.site_description}" />
<meta property="og:url" content="${config.base_url}" />
<meta name="robots" content="index, follow" />
`;

if (!html.includes("google-site-verification")) {
  html = html.replace("</head>", `${seoTags}\n</head>`);
}

fs.writeFileSync(htmlPath, html);

console.log("SEO injected from config.json");
