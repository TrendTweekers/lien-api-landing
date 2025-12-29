import os
import datetime

# Data for 15 new states
states_data = [
    {
        "name": "Kansas",
        "slug": "kansas",
        "notice_req": "Required for suppliers on new residential projects prior to filing lien; not required for commercial",
        "filing_deadline": "3 months from last providing materials",
        "enforcement_deadline": "1 year from lien filing",
        "statutes": "Kan. Stat. §60-1101; §60-1102; §60-1103; §60-1103a; §60-1103b; §60-1105",
        "special": "Warning statement mailed to owner required for lien rights on residential",
        "mistake1": "Missing the Warning Statement on Residential Projects",
        "mistake2": "Filing the lien after 3 months",
        "mistake3": "Missing the 1-year enforcement deadline"
    },
    {
        "name": "Kentucky",
        "slug": "kentucky",
        "notice_req": "Notice to Owner within 75 days of last furnishing (≤ $1,000)",
        "filing_deadline": "6 months from last furnishing",
        "enforcement_deadline": "12 months from lien filing",
        "statutes": "KRS §376.010; §376.080; §376.090",
        "mistake1": "Missing the 75-day Notice to Owner",
        "mistake2": "Filing the lien after 6 months",
        "mistake3": "Missing the 12-month enforcement deadline"
    },
    {
        "name": "Louisiana",
        "slug": "louisiana",
        "notice_req": "Notice of Nonpayment within 75 days of the last day of each month of furnishing",
        "filing_deadline": "60 days from substantial completion (if no Notice of Contract)",
        "enforcement_deadline": "1 year after filing",
        "statutes": "La. R.S. §4801 et seq.; §4802; §4822",
        "special": "Monthly notices: Required",
        "mistake1": "Missing the Monthly Notice of Nonpayment",
        "mistake2": "Filing the lien after 60 days",
        "mistake3": "Missing the 1-year enforcement deadline"
    },
    {
        "name": "Maine",
        "slug": "maine",
        "notice_req": "Not specified",
        "filing_deadline": "90 days after last furnishing (no direct contract)",
        "enforcement_deadline": "120 days after last furnishing",
        "statutes": "10 M.R.S. §3251; §3253; §3255; §3261",
        "mistake1": "Failing to track the 90-day filing window",
        "mistake2": "Filing the lien after 90 days",
        "mistake3": "Missing the 120-day enforcement deadline"
    },
    {
        "name": "Maryland",
        "slug": "maryland",
        "notice_req": "Notice of lien claim within 120 days of last furnishing",
        "filing_deadline": "180 days from last furnishing",
        "enforcement_deadline": "1 year from petition filing",
        "statutes": "Md. Code, Real Prop. §9-104; §9-105; §9-109",
        "mistake1": "Missing the 120-day Notice of Lien Claim",
        "mistake2": "Filing the lien after 180 days",
        "mistake3": "Missing the 1-year enforcement deadline"
    },
    {
        "name": "Massachusetts",
        "slug": "massachusetts",
        "notice_req": "Notice of Identification within 30 days of providing work",
        "filing_deadline": "120 days from last furnishing",
        "enforcement_deadline": "90 days after Statement of Account",
        "statutes": "MGL ch. 254 §4; §8",
        "mistake1": "Missing the 30-day Notice of Identification",
        "mistake2": "Filing the lien after 120 days",
        "mistake3": "Missing the 90-day enforcement deadline"
    },
    {
        "name": "Michigan",
        "slug": "michigan",
        "notice_req": "Notice of Furnishing within 20 days of first furnishing",
        "filing_deadline": "90 days from last furnishing",
        "enforcement_deadline": "1 year from lien filing",
        "statutes": "MCL §570.1101 et seq.; §570.1111",
        "mistake1": "Missing the 20-day Notice of Furnishing",
        "mistake2": "Filing the lien after 90 days",
        "mistake3": "Missing the 1-year enforcement deadline"
    },
    {
        "name": "Minnesota",
        "slug": "minnesota",
        "notice_req": "Preliminary notice within 45 days of first furnishing",
        "filing_deadline": "120 days from last furnishing",
        "enforcement_deadline": "180 days after last furnishing",
        "statutes": "Minn. Stat. §514.01; §514.011; §514.08; §514.13",
        "mistake1": "Missing the 45-day Preliminary Notice",
        "mistake2": "Filing the lien after 120 days",
        "mistake3": "Missing the 180-day enforcement deadline"
    },
    {
        "name": "Mississippi",
        "slug": "mississippi",
        "notice_req": "Within 30 days of first furnishing",
        "filing_deadline": "90 days from last furnishing",
        "enforcement_deadline": "180 days from lien filing",
        "statutes": "Miss. Code §85-7-403; §85-7-405; §85-7-407; §85-7-421",
        "special": "Lien limited to unpaid balance due to GC",
        "mistake1": "Missing the 30-day Notice",
        "mistake2": "Filing the lien after 90 days",
        "mistake3": "Missing the 180-day enforcement deadline"
    },
    {
        "name": "Missouri",
        "slug": "missouri",
        "notice_req": "Disclosure notice prior to first payment",
        "filing_deadline": "6 months after last furnishing",
        "enforcement_deadline": "6 months from filing",
        "statutes": "Mo. Rev. Stat. §429.010; §429.080; §429.100",
        "mistake1": "Missing the Disclosure Notice",
        "mistake2": "Filing the lien after 6 months",
        "mistake3": "Missing the 6-month enforcement deadline"
    },
    {
        "name": "Montana",
        "slug": "montana",
        "notice_req": "Notice of Right to Claim Lien within 20 days of first furnishing",
        "filing_deadline": "90 days from last furnishing",
        "enforcement_deadline": "2 years from filing",
        "statutes": "Mont. Code Ann. §71-3-531; §71-3-535; §71-3-562",
        "mistake1": "Missing the 20-day Notice of Right to Claim Lien",
        "mistake2": "Filing the lien after 90 days",
        "mistake3": "Missing the 2-year enforcement deadline"
    },
    {
        "name": "Nebraska",
        "slug": "nebraska",
        "notice_req": "Not specified",
        "filing_deadline": "120 days after last furnishing",
        "enforcement_deadline": "2 years after filing",
        "statutes": "Neb. Rev. Stat. §52-125; §52-134; §52-137; §52-140",
        "mistake1": "Failing to track the 120-day filing window",
        "mistake2": "Filing the lien after 120 days",
        "mistake3": "Missing the 2-year enforcement deadline"
    },
    {
        "name": "Nevada",
        "slug": "nevada",
        "notice_req": "Notice of Right to Lien after first delivery",
        "filing_deadline": "90 days after completion of work of improvement",
        "enforcement_deadline": "6 months from lien filing",
        "statutes": "NRS §108.221-108.246; §108.239; §108.2415",
        "mistake1": "Missing the Notice of Right to Lien",
        "mistake2": "Filing the lien after 90 days",
        "mistake3": "Missing the 6-month enforcement deadline"
    },
    {
        "name": "New Hampshire",
        "slug": "new-hampshire",
        "notice_req": "Notice of Lien Rights prior to furnishing",
        "filing_deadline": "120 days from last furnishing",
        "enforcement_deadline": "120 days after last furnishing",
        "statutes": "N.H. Rev. Stat. §447:2 et seq.",
        "special": "Written account every 30 days",
        "mistake1": "Missing the Notice of Lien Rights",
        "mistake2": "Filing the lien after 120 days",
        "mistake3": "Missing the 120-day enforcement deadline"
    },
    {
        "name": "New Mexico",
        "slug": "new-mexico",
        "notice_req": "Within 60 days of first furnishing",
        "filing_deadline": "90 days after completion (no direct contract)",
        "enforcement_deadline": "2 years from filing",
        "statutes": "N.M. Stat. §48-2-2; §48-2-6; §48-2-10",
        "mistake1": "Missing the 60-day Notice",
        "mistake2": "Filing the lien after 90 days",
        "mistake3": "Missing the 2-year enforcement deadline"
    }
]

template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{state_name} Lien Deadlines for Material Suppliers | LienDeadline</title>
    <meta name="description" content="{state_name} mechanics lien laws for material suppliers. Know your notice requirements, filing deadlines, and enforcement rules to get paid in {state_name}.">
    <link rel="canonical" href="https://liendeadline.com/state-lien-guides/{state_slug}">
    
    <!-- Open Graph Tags -->
    <meta property="og:title" content="{state_name} Lien Deadlines for Material Suppliers | LienDeadline">
    <meta property="og:description" content="{state_name} mechanics lien laws for material suppliers. Know your notice requirements, filing deadlines, and enforcement rules.">
    <meta property="og:url" content="https://liendeadline.com/state-lien-guides/{state_slug}">
    <meta property="og:type" content="article">
    <meta property="og:image" content="https://liendeadline.com/images/og-share.png">
    
    <!-- Schema.org JSON-LD -->
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "Article",
      "headline": "{state_name} Lien Deadlines for Material Suppliers | LienDeadline",
      "image": [
        "https://liendeadline.com/images/og-share.png"
       ],
      "datePublished": "2025-12-29T12:00:00+00:00",
      "dateModified": "2025-12-29T12:00:00+00:00",
      "author": {{
        "@type": "Organization",
        "name": "LienDeadline",
        "url": "https://liendeadline.com"
      }}
    }}
    </script>
    
    <!-- Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    
    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    
    <style>
        header a[href="/"] {{
            display: block !important;
            height: auto !important;
            line-height: normal !important;
            margin: 0 !important;
            padding: 0 !important;
            text-decoration: none !important;
        }}
        
        header, nav {{ overflow: visible; }}

        .ld-brand{{
            display:flex;
            align-items:center;
            gap:10px;
            text-decoration:none;
            flex:0 0 auto;
            white-space:nowrap;
            min-width:max-content;
        }}
        .ld-brand-icon{{
            height:32px;
            width:auto;
            display:block;
            object-fit:contain;
            flex:0 0 auto;
        }}
        .ld-brand-wordmark{{
            height:28px;
            width:auto;
            display:block;
            object-fit:contain;
            flex:0 0 auto;
        }}

        header{{
            padding:18px 0;
        }}

        @media (max-width:768px){{
            .desktop-nav {{
                display: none !important;
            }}
            header{{ padding:14px 0; }}
            .ld-brand{{ gap:8px; }}
            .ld-brand-icon{{ height:28px; }}
            .ld-brand-wordmark{{ height:24px; }}
        }}

        header img.ld-brand-icon,
        header img.ld-brand-wordmark{{
            max-height:none !important;
        }}
        
        .ld-nav{{
            display:flex;
            justify-content:space-between;
            align-items:center;
            width:100%;
            max-width:1200px;
            margin:0 auto;
            padding:0 16px;
            box-sizing:border-box;
        }}
        @media (max-width:768px){{
            .ld-nav{{ padding:0 12px; }}
        }}
        
        @media (min-width: 769px) {{
            .mobile-menu {{
                display: none !important;
            }}
        }}
    </style>
</head>
<body style="font-family: 'Inter', sans-serif; color: #1F2937;">

    <!-- Header -->
    <header style="background: white; border-bottom: 1px solid #E5E7EB; padding: 16px 0; position: sticky; top: 0; z-index: 1000;">
        <nav class="ld-nav">
            <!-- Logo -->
            <a href="/" class="ld-brand" aria-label="LienDeadline home">
                <img class="ld-brand-icon" src="/images/liendeadline-icon-transparent.png" alt="LienDeadline" />
                <img class="ld-brand-wordmark" src="/images/liendeadline-wordmark-transparent.png" alt="LienDeadline" />
            </a>
            
            <!-- Desktop Nav Links -->
            <div class="desktop-nav" style="display: flex; gap: 32px; align-items: center;">
                <a href="/" style="text-decoration: none; color: #6B7280; font-weight: 500;">Calculator</a>
                <a href="/state-lien-guides.html" style="text-decoration: none; color: #1F2937; font-weight: 600;">State Guides</a>
                <a href="/pricing.html" style="text-decoration: none; color: #6B7280; font-weight: 500;">Pricing</a>
                <a href="/" style="background: #F97316; color: white; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: 600;">Try Free</a>
            </div>
            
        </nav>
        
        <!-- Mobile Menu -->
        <div id="mobileMenu" class="mobile-menu" style="display: none; background: white; border-top: 1px solid #E5E7EB; padding: 16px 24px;">
            <div style="display: flex; flex-direction: column; gap: 16px;">
                <a href="/" style="text-decoration: none; color: #6B7280; font-weight: 500; padding: 8px 0;">Calculator</a>
                <a href="/state-lien-guides.html" style="text-decoration: none; color: #1F2937; font-weight: 600; padding: 8px 0;">State Guides</a>
                <a href="/pricing.html" style="text-decoration: none; color: #6B7280; font-weight: 500; padding: 8px 0;">Pricing</a>
                <a href="/" style="background: #F97316; color: white; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: 600; text-align: center; margin-top: 8px;">Try Free</a>
            </div>
        </div>
    </header>

    <main>
        <!-- Breadcrumbs -->
        <div style="max-width: 800px; margin: 0 auto; padding: 24px 24px 0;">
            <p style="font-size: 14px; color: #6B7280;">
                <a href="/" style="text-decoration: none; color: #6B7280;">Home</a> &gt; 
                <a href="/state-lien-guides.html" style="text-decoration: none; color: #6B7280;">State Guides</a> &gt; 
                <span style="color: #1F2937;">{state_name}</span>
            </p>
        </div>

        <!-- Hero Section -->
        <section style="padding: 40px 24px 60px; text-align: center;">
            <div style="max-width: 800px; margin: 0 auto;">
                <h1 style="font-size: 48px; margin-bottom: 24px; font-weight: 700; color: #1F2937; font-family: 'Instrument Serif', serif;">{state_name} Lien Deadlines for Material Suppliers</h1>
                <p style="font-size: 18px; color: #4B5563; line-height: 1.6; margin-bottom: 32px;">
                    Material suppliers in {state_name} have specific rights to file a mechanics lien if they aren't paid. However, {state_name} law requires strict adherence to notice and filing deadlines. If you miss a deadline by even one day, your lien rights may be extinguished forever. This guide outlines the critical steps for suppliers to secure their payment rights.
                </p>
                
                <!-- High Risk Callout -->
                <div style="background: #FFF7ED; border-left: 4px solid #F97316; padding: 24px; text-align: left; border-radius: 4px; margin-bottom: 40px;">
                    <h3 style="color: #9A3412; font-weight: 700; margin-bottom: 8px; display: flex; align-items: center; gap: 8px;">
                        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
                        Supplier Warning
                    </h3>
                    <p style="color: #9A3412; margin: 0;">
                        {state_name} has strict deadlines. Always calculate your specific deadline based on your last furnishing date.
                    </p>
                </div>

                <!-- Deadlines Table -->
                <div style="border: 1px solid #E5E7EB; border-radius: 8px; overflow: hidden; text-align: left; background: white; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
                    <div style="background: #F9FAFB; padding: 16px 24px; border-bottom: 1px solid #E5E7EB;">
                        <h3 style="font-weight: 600; color: #1F2937; margin: 0;">{state_name} Deadline Overview</h3>
                    </div>
                    
                    <div style="padding: 24px;">
                        <!-- Notice -->
                        <div style="margin-bottom: 24px; padding-bottom: 24px; border-bottom: 1px solid #E5E7EB;">
                            <h4 style="font-size: 14px; text-transform: uppercase; color: #6B7280; font-weight: 600; letter-spacing: 0.5px; margin-bottom: 8px;">1. Preliminary Notice</h4>
                            <p style="font-size: 18px; color: #1F2937; font-weight: 500; margin-bottom: 8px;">{notice_req}</p>
                            <p style="font-size: 14px; color: #4B5563;">Required to preserve your right to file a lien later.</p>
                        </div>

                        <!-- Filing -->
                        <div style="margin-bottom: 24px; padding-bottom: 24px; border-bottom: 1px solid #E5E7EB;">
                            <h4 style="font-size: 14px; text-transform: uppercase; color: #6B7280; font-weight: 600; letter-spacing: 0.5px; margin-bottom: 8px;">2. Lien Filing Deadline</h4>
                            <p style="font-size: 18px; color: #1F2937; font-weight: 500; margin-bottom: 8px;">{filing_deadline}</p>
                            <p style="font-size: 14px; color: #4B5563;">Must be filed with the county recorder/clerk.</p>
                        </div>

                        <!-- Enforcement -->
                        <div style="margin-bottom: 24px; padding-bottom: 24px; border-bottom: 1px solid #E5E7EB;">
                            <h4 style="font-size: 14px; text-transform: uppercase; color: #6B7280; font-weight: 600; letter-spacing: 0.5px; margin-bottom: 8px;">3. Enforcement Deadline</h4>
                            <p style="font-size: 18px; color: #1F2937; font-weight: 500; margin-bottom: 8px;">{enforcement_deadline}</p>
                            <p style="font-size: 14px; color: #4B5563;">Lawsuit to foreclose on the lien must be filed by this date.</p>
                        </div>
                        
                        <!-- Statutes -->
                        <div>
                            <h4 style="font-size: 14px; text-transform: uppercase; color: #6B7280; font-weight: 600; letter-spacing: 0.5px; margin-bottom: 8px;">Governing Statutes</h4>
                            <p style="font-size: 14px; color: #4B5563; font-family: monospace; background: #F3F4F6; padding: 8px; border-radius: 4px; display: inline-block;">
                                {statutes}
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        <!-- Common Mistakes -->
        <section style="background: #F9FAFB; padding: 60px 24px;">
            <div style="max-width: 800px; margin: 0 auto;">
                <h2 style="font-size: 32px; margin-bottom: 32px; font-weight: 700; color: #1F2937; font-family: 'Instrument Serif', serif;">Common Supplier Mistakes in {state_name}</h2>
                
                <div style="display: grid; gap: 24px;">
                    <div style="background: white; padding: 24px; border-radius: 8px; border: 1px solid #E5E7EB;">
                        <h3 style="font-weight: 600; color: #DC2626; margin-bottom: 8px;">❌ {mistake1}</h3>
                        <p style="color: #4B5563;">Many suppliers fail to send the required preliminary notice early in the project, invalidating their future lien rights.</p>
                    </div>
                    
                    <div style="background: white; padding: 24px; border-radius: 8px; border: 1px solid #E5E7EB;">
                        <h3 style="font-weight: 600; color: #DC2626; margin-bottom: 8px;">❌ {mistake2}</h3>
                        <p style="color: #4B5563;">Waiting too long to file. The deadline is strict and often does not extend for weekends or holidays.</p>
                    </div>
                    
                    <div style="background: white; padding: 24px; border-radius: 8px; border: 1px solid #E5E7EB;">
                        <h3 style="font-weight: 600; color: #DC2626; margin-bottom: 8px;">❌ {mistake3}</h3>
                        <p style="color: #4B5563;">Filing a lien is not enough; you must enforce it (file a lawsuit) before the enforcement period expires.</p>
                    </div>
                </div>
            </div>
        </section>

        <!-- CTA Section -->
        <section id="calculator" style="background: #1F2937; color: white; padding: 80px 24px; text-align: center;">
            <div style="max-width: 600px; margin: 0 auto;">
                <h2 style="font-size: 36px; font-weight: 700; margin-bottom: 16px; font-family: 'Instrument Serif', serif;">Don't Guess Your Deadline</h2>
                <p style="font-size: 18px; color: #D1D5DB; margin-bottom: 32px;">
                    {state_name} laws are complex. Our free calculator tells you exactly when your notices and liens are due.
                </p>
                <a href="/" style="background: #F97316; color: white; padding: 16px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 18px; display: inline-block;">
                    Calculate {state_name} Deadline
                </a>
                <p style="margin-top: 16px; font-size: 14px; color: #9CA3AF;">No credit card required • 100% Free</p>
            </div>
        </section>
    </main>

    <!-- Footer -->
    <footer style="background: white; border-top: 1px solid #E5E7EB; padding: 40px 24px; margin-top: auto;">
        <div style="max-width: 1200px; margin: 0 auto; text-align: center;">
            <div style="margin-bottom: 24px;">
                <a href="/" class="ld-brand" style="justify-content:center;" aria-label="LienDeadline home">
                    <img class="ld-brand-icon" src="/images/liendeadline-icon-transparent.png" alt="LienDeadline" />
                    <img class="ld-brand-wordmark" src="/images/liendeadline-wordmark-transparent.png" alt="LienDeadline" />
                </a>
            </div>
            <div style="display: flex; justify-content: center; gap: 24px; margin-bottom: 32px; flex-wrap: wrap;">
                <a href="/" style="color: #6B7280; text-decoration: none;">Calculator</a>
                <a href="/state-lien-guides.html" style="color: #6B7280; text-decoration: none;">State Guides</a>
                <a href="/about" style="color: #6B7280; text-decoration: none;">About</a>
                <a href="/contact" style="color: #6B7280; text-decoration: none;">Contact</a>
                <a href="/privacy" style="color: #6B7280; text-decoration: none;">Privacy</a>
                <a href="/terms" style="color: #6B7280; text-decoration: none;">Terms</a>
            </div>
            <p style="color: #9CA3AF; font-size: 14px; max-width: 600px; margin: 0 auto 16px;">
                <strong>Disclaimer:</strong> LienDeadline is not a law firm and does not provide legal advice. All information is for educational purposes only. Consult with a qualified attorney for legal advice regarding your specific situation.
            </p>
            <p style="color: #9CA3AF; font-size: 14px;">
                &copy; 2025 LienDeadline. All rights reserved.
            </p>
        </div>
    </footer>

</body>
</html>"""

def generate_pages():
    base_dir = "public/state-lien-guides"
    sitemap_entries = []
    hub_cards = []
    
    for state in states_data:
        # Create directory
        state_dir = os.path.join(base_dir, state["slug"])
        os.makedirs(state_dir, exist_ok=True)
        
        # Generate HTML
        html_content = template.format(
            state_name=state["name"],
            state_slug=state["slug"],
            notice_req=state["notice_req"],
            filing_deadline=state["filing_deadline"],
            enforcement_deadline=state["enforcement_deadline"],
            statutes=state["statutes"],
            mistake1=state["mistake1"],
            mistake2=state["mistake2"],
            mistake3=state["mistake3"]
        )
        
        # Write file
        with open(os.path.join(state_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html_content)
            
        print(f"Generated {state['name']}")
        
        # Sitemap Entry
        sitemap_entry = f"""
    <url>
        <loc>https://liendeadline.com/state-lien-guides/{state['slug']}</loc>
        <lastmod>2025-12-29</lastmod>
        <changefreq>monthly</changefreq>
        <priority>0.8</priority>
    </url>"""
        sitemap_entries.append(sitemap_entry)
        
        # Hub Page Card
        card = f"""
                    <a href="/state-lien-guides/{state['slug']}" style="text-decoration: none; color: inherit; display: block; padding: 20px; border: 1px solid #E5E7EB; border-radius: 8px; background: white; transition: all 0.2s ease;" onmouseover="this.style.borderColor='#F97316'; this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(0,0,0,0.08)'" onmouseout="this.style.borderColor='#E5E7EB'; this.style.transform='translateY(0)'; this.style.boxShadow='none'">
                        <h4 style="color: #F97316; margin-bottom: 6px; font-size: 18px; font-weight: 600;">{state['name']}</h4>
                        <p style="font-size: 14px; color: #6B7280;">{state['name']} supplier lien deadlines</p>
                    </a>"""
        hub_cards.append(card)

    # Update Sitemap
    with open("public/sitemap.xml", "r", encoding="utf-8") as f:
        sitemap_content = f.read()
    
    if states_data[0]["slug"] not in sitemap_content:
        insert_pos = sitemap_content.rfind("</urlset>")
        new_sitemap = sitemap_content[:insert_pos] + "\n".join(sitemap_entries) + "\n" + sitemap_content[insert_pos:]
        with open("public/sitemap.xml", "w", encoding="utf-8") as f:
            f.write(new_sitemap)
        print("Updated sitemap.xml")
    
    # Update Hub Page
    with open("public/state-lien-guides.html", "r", encoding="utf-8") as f:
        hub_content = f.read()
        
    if f"/state-lien-guides/{states_data[0]['slug']}" not in hub_content:
        # Find the end of the grid div
        # The grid starts with <div style="display: grid; ..."> and ends with </div>
        # I'll look for the last </a> tag inside the grid and append after it.
        # But wait, finding the closing div of the grid is safer if I can find it.
        # The grid is inside <section id="states"> -> <div class="max-width..."> -> <div style="display: grid...">
        # I can search for the last occurrence of </a> inside the file (which is in the footer) - NO.
        # I can search for the known last state link (Iowa) and insert after it.
        
        last_state = "iowa"
        search_str = f'href="/state-lien-guides/{last_state}"'
        pos = hub_content.find(search_str)
        if pos != -1:
            # Find the closing </a> tag for this link
            end_link_pos = hub_content.find("</a>", pos) + 4
            new_hub = hub_content[:end_link_pos] + "\n" + "\n".join(hub_cards) + hub_content[end_link_pos:]
            with open("public/state-lien-guides.html", "w", encoding="utf-8") as f:
                f.write(new_hub)
            print("Updated state-lien-guides.html")
        else:
            print("Could not find insertion point in state-lien-guides.html")

if __name__ == "__main__":
    generate_pages()
