[1mdiff --git a/index.html b/index.html[m
[1mindex 3f49cc3..444a892 100644[m
[1m--- a/index.html[m
[1m+++ b/index.html[m
[36m@@ -14,6 +14,9 @@[m
     <!-- Tailwind CSS CDN -->[m
     <script src="https://cdn.tailwindcss.com"></script>[m
     [m
[32m+[m[32m    <!-- Lovable Scale Stylesheet (load first) -->[m
[32m+[m[32m    <link rel="stylesheet" href="/lovable-scale.css">[m
[32m+[m[41m    [m
     <script>[m
         tailwind.config = {[m
             theme: {[m
[36m@@ -241,12 +244,7 @@[m
         }[m
         [m
         /* Lovable exact scale overrides */[m
[31m-        [m
[31m-        /* ---------- Typography (from tailwind.config.ts) ---------- */[m
[31m-        html {[m
[31m-            font-family: "Inter", system-ui, sans-serif;[m
[31m-            -webkit-font-smoothing: antialiased;[m
[31m-        }[m
[32m+[m[32m        /* Note: Base html/body styles now in lovable-scale.css */[m
         [m
         h1 {[m
             font-size: 4.5rem;    /* 72px */[m
[36m@@ -319,15 +317,8 @@[m
         [m
         /* Lovable-perfect final override */[m
         [m
[31m-        /* 1. Base reset */[m
[31m-        html {[m
[31m-            font-family: "Inter", system-ui, sans-serif;[m
[31m-            -webkit-font-smoothing: antialiased;[m
[31m-        }[m
[31m-        [m
[31m-        body {[m
[31m-            background: hsl(40 33% 98%);[m
[31m-        }[m
[32m+[m[32m        /* 1. Base reset - Note: Global reset and html font-size now in lovable-scale.css */[m
[32m+[m[32m        /* Override only if needed for specific cases */[m
         [m
         /* 2. Typography scale (exact from repo) */[m
         h1 {[m
[36m@@ -502,7 +493,7 @@[m
             <div class="container mx-auto px-4 sm:px-6 lg:px-8">[m
                 <div class="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">[m
                     <!-- Left: Copy -->[m
[31m-                    <div class="max-w-xl">[m
[32m+[m[32m                    <div class="max-w-screen-xl">[m
                         <!-- Badge -->[m
                         <div class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-secondary border border-border mb-6 animate-fade-up">[m
                             <span class="w-2 h-2 rounded-full bg-success animate-pulse-soft"></span>[m
[36m@@ -774,7 +765,7 @@[m
                     </p>[m
                 </div>[m
                 [m
[31m-                <div class="max-w-3xl mx-auto">[m
[32m+[m[32m                <div class="max-w-screen-xl mx-auto">[m
                     <div class="bg-white rounded-3xl shadow-2xl border border-border p-10 lg:p-12">[m
                         <form id="calculatorForm" class="space-y-8">[m
                             <div class="grid sm:grid-cols-2 gap-6">[m
[36m@@ -868,7 +859,7 @@[m
                     </p>[m
                 </div>[m
                 [m
[31m-                <div class="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">[m
[32m+[m[32m                <div class="grid md:grid-cols-3 gap-8 max-w-screen-xl mx-auto">[m
                     <!-- Starter Plan -->[m
                     <div class="p-8 rounded-2xl border border-border bg-white">[m
                         <h3 class="font-serif text-2xl font-semibold text-foreground mb-2">Starter</h3>[m
[1mdiff --git a/lovable-scale.css b/lovable-scale.css[m
[1mindex f79da74..492e034 100644[m
[1m--- a/lovable-scale.css[m
[1m+++ b/lovable-scale.css[m
[36m@@ -2,15 +2,26 @@[m
    LOVABLE EXACT SCALE - Complete Stylesheet[m
    ============================================ */[m
 [m
[31m-/* ---------- Base Typography ---------- */[m
[32m+[m[32m/* ---------- Global Reset ---------- */[m
[32m+[m[32m*,[m
[32m+[m[32m*::before,[m
[32m+[m[32m*::after {[m
[32m+[m[32m    box-sizing: border-box;[m
[32m+[m[32m    margin: 0;[m
[32m+[m[32m    padding: 0;[m
[32m+[m[32m}[m
[32m+[m
[32m+[m[32m/* ---------- Root Scale (62.5% = 1rem = 10px) ---------- */[m
 html {[m
[31m-    font-family: "Inter", system-ui, sans-serif;[m
[32m+[m[32m    font-family: "Inter", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;[m
[32m+[m[32m    font-size: 62.5%; /* 1rem = 10px */[m
     -webkit-font-smoothing: antialiased;[m
     -moz-osx-font-smoothing: grayscale;[m
 }[m
 [m
 body {[m
     font-family: 'Inter', system-ui, sans-serif;[m
[32m+[m[32m    font-size: 1.6rem; /* 16px base */[m
     background-color: hsl(40 33% 98%);[m
 }[m
 [m
[36m@@ -52,6 +63,25 @@[m [mh3 {[m
     --accent: #f59e0b;              /* amber-500 */[m
     --background: #ffffff;[m
     --border: #e2e8f0;              /* slate-200 */[m
[32m+[m[41m    [m
[32m+[m[32m    /* Spacing Scale */[m
[32m+[m[32m    --space-1: 0.4rem;[m
[32m+[m[32m    --space-2: 0.8rem;[m
[32m+[m[32m    --space-3: 1.2rem;[m
[32m+[m[32m    --space-4: 1.6rem;[m
[32m+[m[32m    --space-5: 2.4rem;[m
[32m+[m[32m    --space-6: 3.2rem;[m
[32m+[m[32m    --space-7: 4.0rem;[m
[32m+[m[32m    --space-8: 4.8rem;[m
[32m+[m[32m}[m
[32m+[m
[32m+[m[32m/* ---------- Container / Max-Width Alignment ---------- */[m
[32m+[m[32m.max-w-screen-xl,[m
[32m+[m[32m.container {[m
[32m+[m[32m    max-width: 1280px;[m
[32m+[m[32m    margin-left: auto;[m
[32m+[m[32m    margin-right: auto;[m
[32m+[m[32m    width: 100%;[m
 }[m
 [m
 /* ---------- Buttons (h-16, text-xl, rounded-xl) ---------- */[m
[36m@@ -117,8 +147,8 @@[m [mselect:focus {[m
 [m
 /* ---------- Section Rhythm ---------- */[m
 section {[m
[31m-    padding-top: 8rem;            /* py-32 */[m
[31m-    padding-bottom: 8rem;[m
[32m+[m[32m    padding-top: 6.4rem;          /* py-32 equivalent with new scale */[m
[32m+[m[32m    padding-bottom: 6.4rem;[m
     scroll-margin-top: 96px;     /* offset for fixed nav */[m
 }[m
 [m
[36m@@ -128,21 +158,21 @@[m [msection + section {[m
 [m
 @media (min-width: 1024px) {[m
     section {[m
[31m-        padding-top: 10rem;       /* lg:py-40 */[m
[31m-        padding-bottom: 10rem;[m
[32m+[m[32m        padding-top: 9.6rem;     /* lg:py-40 equivalent */[m
[32m+[m[32m        padding-bottom: 9.6rem;[m
     }[m
 }[m
 [m
 /* Override only if section doesn't have explicit padding */[m
 section:not([class*="py-"]):not([class*="pt-"]):not([class*="pb-"]) {[m
[31m-    padding-top: 6rem;[m
[31m-    padding-bottom: 6rem;[m
[32m+[m[32m    padding-top: 6.4rem;[m
[32m+[m[32m    padding-bottom: 6.4rem;[m
 }[m
 [m
 @media (min-width: 1024px) {[m
     section:not([class*="py-"]):not([class*="pt-"]):not([class*="pb-"]) {[m
[31m-        padding-top: 8rem;[m
[31m-        padding-bottom: 8rem;[m
[32m+[m[32m        padding-top: 9.6rem;[m
[32m+[m[32m        padding-bottom: 9.6rem;[m
     }[m
 }[m
 [m
