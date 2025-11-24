// calculator.js

// API Base URL (update this to your Railway URL)
const API_BASE = 'https://lien-api-landing-production.up.railway.app';

// Form submission
document.getElementById('calculatorForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    // Get form values
    const invoiceDate = document.getElementById('invoiceDate').value;
    const state = document.getElementById('state').value;
    const role = document.getElementById('role').value;
    
    // Show loading state
    const submitButton = e.target.querySelector('button[type="submit"]');
    const originalText = submitButton.textContent;
    submitButton.textContent = 'Calculating...';
    submitButton.disabled = true;
    
    try {
        // Call API
        const response = await fetch(`${API_BASE}/v1/calculate-deadline?invoice_date=${invoiceDate}&state=${state}&role=${role}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.error) {
            alert(`Error: ${data.error}\n${data.message || ''}`);
            return;
        }
        
        // Display results
        displayResults(data);
        
        // Scroll to results
        document.getElementById('results').scrollIntoView({ behavior: 'smooth' });
        
    } catch (error) {
        console.error('Error:', error);
        alert('Failed to calculate deadlines. Please try again.');
    } finally {
        // Reset button
        submitButton.textContent = originalText;
        submitButton.disabled = false;
    }
});

function displayResults(data) {
    // Show results section
    document.getElementById('results').classList.remove('hidden');
    
    // Preliminary Notice Card
    const prelimCard = document.getElementById('prelimCard');
    const prelimUrgency = data.preliminary_notice.urgency;
    prelimCard.className = `bg-white shadow-lg rounded-lg p-6 border-l-4 ${getUrgencyColor(prelimUrgency)}`;
    
    document.getElementById('prelimTitle').textContent = data.preliminary_notice.name;
    document.getElementById('prelimDate').textContent = formatDate(data.preliminary_notice.deadline);
    document.getElementById('prelimDays').textContent = `${data.preliminary_notice.days_from_now} days`;
    document.getElementById('prelimDays').className = `text-2xl font-bold ${getUrgencyTextColor(prelimUrgency)}`;
    document.getElementById('prelimDescription').textContent = data.preliminary_notice.description;
    
    // Lien Filing Card
    const lienCard = document.getElementById('lienCard');
    const lienUrgency = data.lien_filing.urgency;
    lienCard.className = `bg-white shadow-lg rounded-lg p-6 border-l-4 ${getUrgencyColor(lienUrgency)}`;
    
    document.getElementById('lienTitle').textContent = data.lien_filing.name;
    document.getElementById('lienDate').textContent = formatDate(data.lien_filing.deadline);
    document.getElementById('lienDays').textContent = `${data.lien_filing.days_from_now} days`;
    document.getElementById('lienDays').className = `text-2xl font-bold ${getUrgencyTextColor(lienUrgency)}`;
    document.getElementById('lienDescription').textContent = data.lien_filing.description;
    
    // Serving Requirements
    const servingList = document.getElementById('servingList');
    servingList.innerHTML = '';
    data.serving_requirements.forEach(req => {
        const li = document.createElement('li');
        li.className = 'flex items-center text-gray-700';
        li.innerHTML = `
            <svg class="h-5 w-5 text-green-500 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
            </svg>
            ${formatServing(req)}
        `;
        servingList.appendChild(li);
    });
    
    // Critical Warnings
    const warningsList = document.getElementById('warningsList');
    warningsList.innerHTML = '';
    if (data.critical_warnings && data.critical_warnings.length > 0) {
        data.critical_warnings.forEach(warning => {
            const li = document.createElement('li');
            li.className = 'text-red-700 text-sm';
            li.textContent = warning;
            warningsList.appendChild(li);
        });
    } else {
        document.getElementById('warningsSection').classList.add('hidden');
    }
    
    // Statute Citations
    const citationsList = document.getElementById('citationsList');
    citationsList.innerHTML = '';
    data.statute_citations.forEach(citation => {
        const li = document.createElement('li');
        li.textContent = citation;
        citationsList.appendChild(li);
    });
    
    // Store data for PDF/Email
    window.currentCalculation = data;
}

function getUrgencyColor(urgency) {
    switch(urgency) {
        case 'critical': return 'border-red-500';
        case 'warning': return 'border-yellow-500';
        default: return 'border-green-500';
    }
}

function getUrgencyTextColor(urgency) {
    switch(urgency) {
        case 'critical': return 'text-red-600';
        case 'warning': return 'text-yellow-600';
        default: return 'text-green-600';
    }
}

function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { 
        weekday: 'long', 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
    });
}

function formatServing(requirement) {
    const map = {
        'property_owner': 'Property Owner',
        'original_contractor': 'Original Contractor',
        'direct_contractor': 'Direct Contractor',
        'construction_lender': 'Construction Lender'
    };
    return map[requirement] || requirement;
}

// PDF Download (we'll implement this next)
document.getElementById('downloadPDF').addEventListener('click', () => {
    alert('PDF download feature coming in next step!');
});

// Email Report (we'll implement this next)
document.getElementById('emailReport').addEventListener('click', () => {
    alert('Email feature coming in next step!');
});

// Set today as default invoice date
document.getElementById('invoiceDate').valueAsDate = new Date();

