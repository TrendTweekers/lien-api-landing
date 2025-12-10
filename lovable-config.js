// Tailwind Config - Lovable Scale
// Paste this into your tailwind.config.js or use inline in <script> tag

tailwind.config = {
    theme: {
        extend: {
            colors: {
                background: 'hsl(40 33% 98%)',
                foreground: 'hsl(220 20% 15%)',
                primary: 'hsl(220 60% 20%)',
                'primary-foreground': 'hsl(40 33% 98%)',
                secondary: 'hsl(40 30% 94%)',
                'secondary-foreground': 'hsl(220 20% 15%)',
                accent: 'hsl(16 85% 55%)',
                'accent-foreground': 'hsl(0 0% 100%)',
                success: 'hsl(152 60% 42%)',
                warning: 'hsl(38 95% 50%)',
                muted: 'hsl(40 20% 92%)',
                'muted-foreground': 'hsl(220 10% 45%)',
                border: 'hsl(40 20% 88%)',
            },
            fontFamily: {
                serif: ['Instrument Serif', 'serif'],
                sans: ['Inter', 'system-ui', 'sans-serif'],
            }
        }
    }
}

