import { addDays, isWeekend, getMonth, getYear, addMonths, setDate, startOfMonth, subDays, isSameMonth, getDate } from "date-fns";
import { STATE_RULES } from "./stateRules";

// --- Holiday Logic (Simplified US Federal Holidays) ---
// Note: Ideally this would come from a robust library, but for this refactor we implement standard rules.

function getFloatingHoliday(year: number, month: number, week: number, dayOfWeek: number): Date {
  // week: 1 = 1st, 2 = 2nd, 3 = 3rd, 4 = 4th, -1 = last
  const firstDay = startOfMonth(new Date(year, month));
  let date = firstDay;
  
  // Find first occurrence of dayOfWeek
  while (date.getDay() !== dayOfWeek) {
    date = addDays(date, 1);
  }
  
  if (week === -1) {
    // Logic for last occurrence: go to next month and backtrack? 
    // Easier: find all occurrences and take last.
    // Re-implementing simplified logic for specific holidays below is safer.
    return date; // Placeholder, not used in simplified main logic below
  }

  return addDays(date, (week - 1) * 7);
}

function getMemorialDay(year: number): Date {
  // Last Monday in May (Month 4)
  let date = new Date(year, 4, 31); // May 31
  while (date.getDay() !== 1) { // 1 = Monday
    date = subDays(date, 1);
  }
  return date;
}

function isSameDate(d1: Date, d2: Date): boolean {
  return getYear(d1) === getYear(d2) && getMonth(d1) === getMonth(d2) && getDate(d1) === getDate(d2);
}

function isHoliday(date: Date): boolean {
  const year = getYear(date);
  const holidays: Date[] = [];

  // Fixed Holidays
  const fixed = [
    new Date(year, 0, 1),   // New Year's Day
    new Date(year, 5, 19),  // Juneteenth
    new Date(year, 6, 4),   // Independence Day
    new Date(year, 10, 11), // Veterans Day
    new Date(year, 11, 25), // Christmas Day
  ];

  for (const h of fixed) {
    holidays.push(h);
    const day = h.getDay(); // 0=Sun, 6=Sat
    // Observed logic
    if (day === 6) holidays.push(subDays(h, 1)); // Sat -> Fri
    if (day === 0) holidays.push(addDays(h, 1)); // Sun -> Mon
  }

  // Floating Holidays
  holidays.push(getFloatingHoliday(year, 0, 3, 1));  // MLK Jr (3rd Mon Jan)
  holidays.push(getFloatingHoliday(year, 1, 3, 1));  // Presidents (3rd Mon Feb)
  holidays.push(getMemorialDay(year));               // Memorial (Last Mon May)
  holidays.push(getFloatingHoliday(year, 8, 1, 1));  // Labor (1st Mon Sept)
  holidays.push(getFloatingHoliday(year, 9, 2, 1));  // Columbus (2nd Mon Oct)
  holidays.push(getFloatingHoliday(year, 10, 4, 4)); // Thanksgiving (4th Thu Nov)

  return holidays.some(h => isSameDate(date, h));
}

function isBusinessDay(date: Date): boolean {
  const day = date.getDay();
  const isWeekend = day === 0 || day === 6; // 0=Sun, 6=Sat
  return !isWeekend && !isHoliday(date);
}

function getNextBusinessDay(date: Date): Date {
  let d = new Date(date);
  while (!isBusinessDay(d)) {
    d = addDays(d, 1);
  }
  return d;
}

export function adjustForBusinessDays(date: Date): Date {
  return getNextBusinessDay(date);
}

// --- Specific State Logic ---

function calculateTexas(invoiceDate: Date, projectType: "residential" | "commercial"): { prelim: Date; lien: Date } {
  // Prelim:
  // Commercial: 15th of 3rd month following (Offset 3)
  // Residential: 15th of 2nd month following (Offset 2)
  const prelimMonthOffset = projectType === "residential" ? 2 : 3;
  let prelim = setDate(addMonths(invoiceDate, prelimMonthOffset), 15);
  prelim = getNextBusinessDay(prelim);

  // Lien:
  // Commercial: 15th of 4th month following (Offset 4)
  // Residential: 15th of 3rd month following (Offset 3)
  const lienMonthOffset = projectType === "residential" ? 3 : 4;
  let lien = setDate(addMonths(invoiceDate, lienMonthOffset), 15);
  lien = getNextBusinessDay(lien);

  return { prelim, lien };
}

function calculateWashington(invoiceDate: Date): { prelim: Date; lien: Date } {
  // Prelim: 60 days
  let prelim = addDays(invoiceDate, 60);
  prelim = getNextBusinessDay(prelim);

  // Lien: 90 days
  let lien = addDays(invoiceDate, 90);
  lien = getNextBusinessDay(lien);

  return { prelim, lien };
}

function calculateCalifornia(invoiceDate: Date): { prelim: Date; lien: Date } {
  // Prelim: 20 days
  let prelim = addDays(invoiceDate, 20);
  prelim = getNextBusinessDay(prelim);
  
  // Lien: 90 days
  let lien = addDays(invoiceDate, 90);
  lien = getNextBusinessDay(lien);

  return { prelim, lien };
}

// --- Main Calculator Function ---

export interface DeadlineResult {
  preliminaryNotice: Date;
  lienFiling: Date;
}

export function calculateStateDeadline(
  stateCode: string,
  invoiceDate: Date,
  projectType: "residential" | "commercial" = "commercial",
  role: "supplier" | "subcontractor" = "supplier"
): DeadlineResult {
  const code = stateCode.toUpperCase();
  const rule = STATE_RULES.find((r) => r.state_code === code);

  if (!rule) {
    // Fallback if no rule found
    return {
      preliminaryNotice: addDays(invoiceDate, 30),
      lienFiling: addDays(invoiceDate, 90),
    };
  }

  // Custom State Handlers
  if (code === "TX") {
    const res = calculateTexas(invoiceDate, projectType);
    return { preliminaryNotice: res.prelim, lienFiling: res.lien };
  }
  if (code === "WA") {
    const res = calculateWashington(invoiceDate);
    return { preliminaryNotice: res.prelim, lienFiling: res.lien };
  }
  if (code === "CA") {
    const res = calculateCalifornia(invoiceDate);
    return { preliminaryNotice: res.prelim, lienFiling: res.lien };
  }

  // Default Logic based on DB Rules
  let prelimDate: Date;
  if (rule.preliminary_notice.deadline_days) {
    prelimDate = addDays(invoiceDate, rule.preliminary_notice.deadline_days);
  } else {
    // If no days specified (e.g. formula or null), default to 30 as safety or null?
    // Let's use 30 as a safe default for display if unknown
    prelimDate = addDays(invoiceDate, 30);
  }

  let lienDate: Date;
  if (rule.lien_filing.deadline_days) {
    lienDate = addDays(invoiceDate, rule.lien_filing.deadline_days);
  } else {
    lienDate = addDays(invoiceDate, 90);
  }

  // Apply Weekend/Holiday Extensions if allowed
  if (rule.special_rules.weekend_extension || rule.special_rules.holiday_extension) {
    // If extension allowed, we move to next business day if it lands on non-business day
    // Note: Some states only extend for weekends, some for holidays.
    // For simplicity, if either is true, we usually check for that specific type.
    // But commonly, "Next Business Day" covers both.
    
    // Check if we need to extend
    if (rule.special_rules.weekend_extension && isWeekend(prelimDate)) {
      prelimDate = getNextBusinessDay(prelimDate);
    } else if (rule.special_rules.holiday_extension && isHoliday(prelimDate)) {
      prelimDate = getNextBusinessDay(prelimDate);
    }

    if (rule.special_rules.weekend_extension && isWeekend(lienDate)) {
      lienDate = getNextBusinessDay(lienDate);
    } else if (rule.special_rules.holiday_extension && isHoliday(lienDate)) {
      lienDate = getNextBusinessDay(lienDate);
    }
  }

  return {
    preliminaryNotice: prelimDate,
    lienFiling: lienDate,
  };
}
