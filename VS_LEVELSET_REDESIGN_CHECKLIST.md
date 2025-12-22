# vs-levelset.html Redesign Checklist

## ✅ Completed Changes

### 1. Feature Flag System
- ✅ Added `COMPARE_V2` feature flag at top of `<body>` (line ~408)
- ✅ Set to `'on'` by default (can be changed to `'off'` to revert)
- ✅ Version toggle script handles display logic

### 2. SEO Preservation
- ✅ All `<head>` meta tags preserved (title, description, OpenGraph, canonical)
- ✅ FAQ Schema JSON-LD preserved (lines 357-405)
- ✅ No changes to SEO-critical content

### 3. V2 Design Implementation
- ✅ Created `#compare-page` wrapper with scoped CSS
- ✅ Hero section with centered headline and subtitle
- ✅ Comparison table with clean, modern styling
- ✅ CTA section with gradient background
- ✅ FAQ accordion with interactive toggle functionality
- ✅ All styles scoped to `#compare-page` (no global CSS conflicts)

### 4. V1 Preservation
- ✅ Original content wrapped in `#compare-v1` container
- ✅ All original IDs, classes, and structure preserved
- ✅ Original CSS remains intact
- ✅ Conditional display based on feature flag

### 5. Links & Functionality
- ✅ CTA button preserves `/calculator.html?ref=[REF_CODE]` link
- ✅ Referral code handler script preserved (lines 800-825)
- ✅ All internal navigation links preserved
- ✅ Footer links preserved

### 6. Responsive Design
- ✅ Mobile-responsive comparison table (horizontal scroll on small screens)
- ✅ Responsive typography (smaller headings on mobile)
- ✅ Touch-friendly FAQ accordion buttons

## 📋 Testing Checklist

### Feature Flag Testing
- [ ] Set `COMPARE_V2 = 'off'` - verify V1 displays correctly
- [ ] Set `COMPARE_V2 = 'on'` - verify V2 displays correctly
- [ ] Verify only one version displays at a time

### Link Testing
- [ ] CTA button navigates to `/calculator.html`
- [ ] Referral code handler works with `?ref=` parameter
- [ ] Footer links work correctly
- [ ] Header navigation links work correctly

### Functionality Testing
- [ ] FAQ accordion toggles open/close correctly
- [ ] Only one FAQ item open at a time
- [ ] FAQ animations work smoothly

### Visual Testing
- [ ] Comparison table displays correctly on desktop
- [ ] Comparison table scrolls horizontally on mobile
- [ ] CTA section gradient displays correctly
- [ ] Badges display with correct colors
- [ ] Typography matches Lovable design

### Browser Testing
- [ ] Chrome/Edge
- [ ] Firefox
- [ ] Safari
- [ ] Mobile browsers (iOS Safari, Chrome Mobile)

## 🎨 Design Changes Summary

### V2 Design Features
1. **Hero Section**: Centered headline with subtitle
2. **Comparison Table**: Clean table format instead of cards
3. **Badges**: Color-coded badges (green=success, yellow=warning, gray=neutral)
4. **CTA Section**: Gradient background with white button
5. **FAQ Accordion**: Interactive expand/collapse instead of static list

### CSS Scoping
- All V2 styles prefixed with `#compare-page`
- No global CSS modifications
- Original styles remain untouched

## 🔧 How to Toggle Versions

### Enable V2 (New Design)
```javascript
window.COMPARE_V2 = 'on';
```

### Enable V1 (Original Design)
```javascript
window.COMPARE_V2 = 'off';
```

Or edit the script tag at line ~408:
```html
<!-- COMPARE_V2: on -->
<script>
    window.COMPARE_V2 = 'on';  // Change to 'off' for V1
</script>
```

## 📝 Files Modified

- `vs-levelset.html` - Added V2 layout, scoped CSS, feature flag system

## 🚀 Next Steps

1. Test both versions in production
2. Monitor analytics for user engagement
3. Gather feedback on V2 design
4. Decide on permanent switch to V2 or further iterations

