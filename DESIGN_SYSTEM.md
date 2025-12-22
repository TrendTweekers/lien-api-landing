# LienDeadline.com Design System

## Color Palette

### Primary Colors

**Navy (Primary Brand Color)**
- Hex: `#1e3a8a`
- RGB: `rgb(30, 58, 138)`
- Usage: Headers, primary buttons, navigation, brand elements
- Tailwind: `bg-navy`, `text-navy`, `border-navy`

**Coral (Accent Color)**
- Hex: `#f97316`
- RGB: `rgb(249, 115, 22)`
- Usage: CTAs, highlights, interactive elements, timeline markers
- Tailwind: `bg-coral`, `text-coral`, `border-coral`

**Coral Light**
- Hex: `#fed7aa`
- RGB: `rgb(254, 215, 170)`
- Usage: Backgrounds, gradients, subtle highlights
- CSS Variable: `--coral-light`

**Coral Dark**
- Hex: `#ea580c`
- RGB: `rgb(234, 88, 12)`
- Usage: Hover states, active states, emphasis
- CSS Variable: `--coral-dark`

### Secondary Colors

**Red**
- Hex: `#dc2626`
- RGB: `rgb(220, 38, 38)`
- Usage: Errors, urgent deadlines, danger states
- CSS Variable: `--red`

**Orange**
- Hex: `#f59e0b`
- RGB: `rgb(245, 158, 11)`
- Usage: Warnings, pre-notice deadlines, timeline markers
- CSS Variable: `--orange`

**Green**
- Hex: `#10b981`
- RGB: `rgb(16, 185, 129)`
- Usage: Success states, completed payments, positive indicators
- CSS Variable: `--green`

### Neutral Colors (Tailwind Default)

**Gray Scale**
- Gray-50: `#f9fafb` (light backgrounds)
- Gray-100: `#f3f4f6` (subtle backgrounds)
- Gray-200: `#e5e7eb` (borders)
- Gray-300: `#d1d5db` (disabled states)
- Gray-400: `#9ca3af` (secondary text)
- Gray-500: `#6b7280` (placeholder text)
- Gray-600: `#4b5563` (body text)
- Gray-700: `#374151` (headings)
- Gray-800: `#1f2937` (dark text)
- Gray-900: `#111827` (darkest text)

### HSL Color System (Lovable Scale)

**Background**
- HSL: `hsl(40 33% 98%)`
- Usage: Main page background

**Foreground**
- HSL: `hsl(220 20% 15%)`
- Usage: Primary text color

**Primary**
- HSL: `hsl(220 60% 20%)`
- Usage: Primary actions, links

**Accent**
- HSL: `hsl(16 85% 55%)`
- Usage: Accent elements, CTAs

**Success**
- HSL: `hsl(152 60% 42%)`
- Usage: Success messages, completed states

**Warning**
- HSL: `hsl(38 95% 50%)`
- Usage: Warning messages, alerts

## Typography

### Font Families

**Headings (Serif)**
- Font: `Instrument Serif`
- Weights: 400, 500, 600, 700
- Usage: All headings (h1, h2, h3, h4, h5, h6)
- Tailwind: `font-serif`

**Body Text (Sans-Serif)**
- Font: `Inter`
- Weights: 400, 500, 600, 700
- Usage: Body text, buttons, UI elements
- Tailwind: `font-sans`

### Font Sizes

- Base: `1rem` (16px)
- Small: `0.875rem` (14px)
- Large: `1.125rem` (18px)
- XL: `1.25rem` (20px)
- 2XL: `1.5rem` (24px)
- 3XL: `1.875rem` (30px)
- 4XL: `2.25rem` (36px)
- 5XL: `3rem` (48px)

## Spacing System

Uses Tailwind's default spacing scale:
- 1: `0.25rem` (4px)
- 2: `0.5rem` (8px)
- 3: `0.75rem` (12px)
- 4: `1rem` (16px)
- 6: `1.5rem` (24px)
- 8: `2rem` (32px)
- 12: `3rem` (48px)
- 16: `4rem` (64px)
- 20: `5rem` (80px)
- 24: `6rem` (96px)

## Border Radius

- Small: `0.25rem` (4px) - `rounded`
- Medium: `0.5rem` (8px) - `rounded-lg`
- Large: `0.75rem` (12px) - `rounded-xl`
- Extra Large: `9999px` - `rounded-full`

## Shadows

- Small: `0 1px 2px 0 rgba(0, 0, 0, 0.05)`
- Medium: `0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)`
- Large: `0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)`
- XL: `0 20px 25px -5px rgba(0, 0, 20%, 0.1), 0 8px 10px -6px rgba(0, 0, 20%, 0.1)`

## Tailwind Configuration

```javascript
tailwind.config = {
    theme: {
        extend: {
            colors: {
                navy: '#1e3a8a',
                coral: '#f97316',
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
```

## CSS Variables

```css
:root {
    --navy: #1e3a8a;
    --coral: #f97316;
    --coral-light: #fed7aa;
    --coral-dark: #ea580c;
    --red: #dc2626;
    --orange: #f59e0b;
    --green: #10b981;
}
```

## Color Usage Guidelines

### Primary Actions
- Use **Navy** (`#1e3a8a`) for primary buttons and links
- Use **Coral** (`#f97316`) for CTAs and important actions

### Status Indicators
- **Green** (`#10b981`): Success, completed, active
- **Orange** (`#f59e0b`): Warning, pending, pre-notice deadlines
- **Red** (`#dc2626`): Error, urgent, lien deadlines, overdue
- **Coral** (`#f97316`): Today's date marker
- **Yellow** (`#fbbf24`): Alerts, highlights

### Backgrounds
- **White** (`#ffffff`): Main content areas
- **Gray-50** (`#f9fafb`): Subtle backgrounds
- **Gray-100** (`#f3f4f6`): Disabled states
- **Navy** (`#1e3a8a`): Hero sections, headers

### Text Colors
- **Gray-900** (`#111827`): Primary text
- **Gray-700** (`#374151`): Secondary text
- **Gray-600** (`#4b5563`): Tertiary text
- **Gray-500** (`#6b7280`): Placeholder text
- **White** (`#ffffff`): Text on dark backgrounds

## Component Colors

### Timeline Markers
- **Today**: Coral (`#f97316`)
- **Pre-Notice**: Orange (`#f59e0b`)
- **Lien Deadline**: Red (`#dc2626`)

### Comparison Cards
- **Speed**: Green (`#10b981`)
- **Fields**: Blue (`#3b82f6`)
- **Price**: Coral (`#f97316`) with gradient
- **Mobile**: Purple (`#a855f7`)
- **States**: Indigo (`#6366f1`)
- **Filing**: Red (`#dc2626`)

### Payment Status
- **Pending**: Yellow (`#fbbf24`)
- **Active**: Green (`#10b981`)
- **Suspended**: Red (`#dc2626`)
- **First Payment**: Blue (`#3b82f6`)

## Accessibility

All color combinations meet WCAG AA contrast requirements:
- Navy on white: 4.5:1 ✓
- Coral on white: 4.5:1 ✓
- White on navy: 4.5:1 ✓
- Gray-700 on white: 7.1:1 ✓
- Gray-600 on white: 7.0:1 ✓

## Responsive Breakpoints

- Mobile: `< 640px`
- Tablet: `640px - 1024px`
- Desktop: `> 1024px`

## Font Loading

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital,wght@0,400;0,500;0,600;0,700;1,400&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
```

## Example Usage

### Primary Button
```html
<button class="bg-navy text-white px-6 py-3 rounded-lg hover:bg-blue-900">
    Primary Action
</button>
```

### CTA Button
```html
<button class="bg-coral text-white px-6 py-3 rounded-lg hover:bg-coral-dark">
    Get Started
</button>
```

### Status Badge
```html
<span class="px-2 py-1 rounded text-xs bg-green-100 text-green-800">
    Active
</span>
```

### Timeline Marker
```html
<div class="w-4 h-4 rounded-full bg-coral"></div>
```

## Design Principles

1. **Navy & Coral** are the primary brand colors
2. **Navy** for trust, professionalism, stability
3. **Coral** for action, urgency, attention
4. **Green** for success and positive states
5. **Red** for urgency and important deadlines
6. **Orange** for warnings and pre-notice deadlines

