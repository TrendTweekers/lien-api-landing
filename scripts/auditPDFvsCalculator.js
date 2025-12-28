const axios = require('axios');
const fs = require('fs');

const STATES = ['UT', 'CA', 'TX', 'FL', 'NY', 'WA', 'OR', 'OH', 'HI', 'AK'];
const TEST_DATE = '2025-12-27';
const API_BASE = process.env.API_BASE || 'http://localhost:8000';

async function audit() {
  const results = [];
  
  for (const state of STATES) {
    try {
      // 1. Get calculator result
      const calcRes = await axios.post(`${API_BASE}/api/v1/calculate-deadline`, {
        state,
        invoice_date: TEST_DATE,
        role: 'supplier'
      });
      
      // 2. Get PDF result (parse from PDF)
      const pdfRes = await axios.get(
        `${API_BASE}/api/v1/guide/${state}/pdf?invoice_date=${TEST_DATE}`,
        { responseType: 'arraybuffer' }  // Get binary PDF data
      );
      
      // 3. Parse PDF text (extract deadline lines)
      // Note: This is a simplified parser - you may need pdf-parse or similar library
      const pdfBuffer = Buffer.from(pdfRes.data);
      const pdfText = pdfBuffer.toString('utf8'); // Try to extract text
      
      // Look for deadline patterns in PDF text
      const prelimMatch = pdfText.match(/Preliminary Notice Deadline:\s*([A-Za-z]+\s+\d+,\s+\d{4})/i);
      const lienMatch = pdfText.match(/Lien Filing Deadline:\s*([A-Za-z]+\s+\d+,\s+\d{4})/i);
      
      // Convert calculator dates to same format for comparison
      const calcPrelim = calcRes.data.preliminary_deadline ? 
        new Date(calcRes.data.preliminary_deadline).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }) : 
        null;
      const calcLien = calcRes.data.lien_deadline ? 
        new Date(calcRes.data.lien_deadline).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }) : 
        null;
      
      const prelimMatchStr = prelimMatch ? prelimMatch[1] : 'Not found';
      const lienMatchStr = lienMatch ? lienMatch[1] : 'Not found';
      
      const prelimMatchBool = calcPrelim && prelimMatchStr ? 
        calcPrelim.toLowerCase() === prelimMatchStr.toLowerCase() : 
        (calcPrelim === null && prelimMatchStr === 'Not found');
      
      const lienMatchBool = calcLien && lienMatchStr ? 
        calcLien.toLowerCase() === lienMatchStr.toLowerCase() : 
        (calcLien === null && lienMatchStr === 'Not found');
      
      const match = prelimMatchBool && lienMatchBool;
      
      const mismatch = {
        state,
        match: match,
        calculator: {
          prelim_deadline: calcPrelim,
          lien_deadline: calcLien,
          prelim_days_remaining: calcRes.data.prelim_days_remaining,
          lien_days_remaining: calcRes.data.lien_days_remaining
        },
        pdf: {
          prelim_deadline: prelimMatchStr,
          lien_deadline: lienMatchStr
        },
        details: {
          prelim_match: prelimMatchBool,
          lien_match: lienMatchBool
        }
      };
      
      results.push(mismatch);
      console.log(`${state}: ${match ? '✅ MATCH' : '❌ MISMATCH'}`);
      if (!match) {
        console.log(`  Calculator: Prelim=${calcPrelim}, Lien=${calcLien}`);
        console.log(`  PDF: Prelim=${prelimMatchStr}, Lien=${lienMatchStr}`);
      }
      
    } catch (e) {
      console.error(`${state}: ERROR - ${e.message}`);
      results.push({ state, error: e.message, stack: e.stack });
    }
  }
  
  fs.writeFileSync('pdf-audit-results.json', JSON.stringify(results, null, 2));
  const mismatches = results.filter(r => !r.match && !r.error);
  console.log(`\n✅ Total Matches: ${results.length - mismatches.length}/${STATES.length}`);
  console.log(`❌ Total Mismatches: ${mismatches.length}/${STATES.length}`);
  
  if (mismatches.length > 0) {
    console.log('\nMismatched States:');
    mismatches.forEach(m => {
      console.log(`  - ${m.state}: Prelim=${m.details.prelim_match ? '✅' : '❌'}, Lien=${m.details.lien_match ? '✅' : '❌'}`);
    });
  }
}

audit().catch(console.error);

