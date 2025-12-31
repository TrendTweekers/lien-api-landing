export interface StateRule {
  state_code: string;
  state_name: string;
  preliminary_notice: {
    required: boolean;
    deadline_description: string | null;
    deadline_days: number | null;
    deadline_formula: string | null;
    statute: string | null;
  };
  lien_filing: {
    deadline_description: string;
    deadline_days: number;
    deadline_formula: string | null;
    statute: string | null;
  };
  special_rules: {
    weekend_extension: boolean;
    holiday_extension: boolean;
    residential_vs_commercial: boolean;
    notice_of_completion_trigger: boolean;
    notes: string;
  };
}

export const STATE_RULES: StateRule[] = [
  {
    state_code: "AL",
    state_name: "Alabama",
    preliminary_notice: {
      required: true,
      deadline_description: "Prior to supplying materials (optional for enhanced rights)",
      deadline_days: null,
      deadline_formula: null,
      statute: "Ala. Code §35-11-215"
    },
    lien_filing: {
      deadline_description: "4 months after last providing materials",
      deadline_days: 120,
      deadline_formula: null,
      statute: "Ala. Code §35-11-215"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: false,
      notice_of_completion_trigger: false,
      notes: ""
    }
  },
  {
    state_code: "AK",
    state_name: "Alaska",
    preliminary_notice: {
      required: true,
      deadline_description: "Before furnishing labor or materials",
      deadline_days: null,
      deadline_formula: null,
      statute: "AS 34.35.064"
    },
    lien_filing: {
      deadline_description: "120 days after last furnishing of materials",
      deadline_days: 120,
      deadline_formula: null,
      statute: "AS 34.35.068(a)"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: false,
      notice_of_completion_trigger: true,
      notes: "If owner records Notice of Completion, deadline may shorten to 15 days for some claimants"
    }
  },
  {
    state_code: "AR",
    state_name: "Arkansas",
    preliminary_notice: {
      required: true,
      deadline_description: "within 75 days of last furnishing work and materials on commercial projects",
      deadline_days: 75,
      deadline_formula: null,
      statute: "Ark. Code §18-44-115(b)(5)"
    },
    lien_filing: {
      deadline_description: "within 120 days after last furnishing labor or materials",
      deadline_days: 120,
      deadline_formula: null,
      statute: "Ark. Code §18-44-117(a)(1)"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: true,
      notice_of_completion_trigger: false,
      notes: "Notice of Intent to Lien required at least 10 days before filing. On residential: Pre-Construction Notice required prior to work."
    }
  },
  {
    state_code: "AZ",
    state_name: "Arizona",
    preliminary_notice: {
      required: true,
      deadline_description: "Within 20 days of first providing materials",
      deadline_days: 20,
      deadline_formula: null,
      statute: "Ariz. Rev. Stat. § 33-992.01"
    },
    lien_filing: {
      deadline_description: "120 days from completion; 60 days if notice of completion filed",
      deadline_days: 120,
      deadline_formula: null,
      statute: "Ariz. Rev. Stat. § 33-993"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: false,
      notice_of_completion_trigger: true,
      notes: "If Notice of Completion filed, deadline shortens to 60 days"
    }
  },
  {
    state_code: "CA",
    state_name: "California",
    preliminary_notice: {
      required: true,
      deadline_description: "20 days from first providing materials",
      deadline_days: 20,
      deadline_formula: null,
      statute: "Cal. Civ. Code §8204(a)"
    },
    lien_filing: {
      deadline_description: "Earlier of 90 days after completion or 30 days after notice of completion",
      deadline_days: 90,
      deadline_formula: null,
      statute: "Cal. Civ. Code §8414"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: false,
      notice_of_completion_trigger: true,
      notes: "CRITICAL: If Notice of Completion filed, deadline shortens to 30 days"
    }
  },
  {
    state_code: "CO",
    state_name: "Colorado",
    preliminary_notice: {
      required: true,
      deadline_description: "At least 10 days before filing the lien",
      deadline_days: 10,
      deadline_formula: null,
      statute: "C.R.S. § 38-22-109(3)"
    },
    lien_filing: {
      deadline_description: "4 months after last materials provided",
      deadline_days: 120,
      deadline_formula: "4 months",
      statute: "C.R.S. § 38-22-109(5)"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: true,
      notice_of_completion_trigger: false,
      notes: "2 months for one or two-family homes if bona fide purchaser"
    }
  },
  {
    state_code: "CT",
    state_name: "Connecticut",
    preliminary_notice: {
      required: true,
      deadline_description: "Notice of Intent to owner and prime contractor within 90 days after ceasing work",
      deadline_days: 90,
      deadline_formula: null,
      statute: "Conn. Gen. Stat. §49-33"
    },
    lien_filing: {
      deadline_description: "90 days of the date of last furnishing labor or materials",
      deadline_days: 90,
      deadline_formula: null,
      statute: "Conn. Gen. Stat. §49-34"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: true,
      notice_of_completion_trigger: false,
      notes: "Residential projects: Notice of Intent required"
    }
  },
  {
    state_code: "DE",
    state_name: "Delaware",
    preliminary_notice: {
      required: false,
      deadline_description: null,
      deadline_days: null,
      deadline_formula: null,
      statute: null
    },
    lien_filing: {
      deadline_description: "120 days from last supplied materials or performed labor",
      deadline_days: 120,
      deadline_formula: null,
      statute: "25 Del. C. § 2711(b)"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: false,
      notice_of_completion_trigger: false,
      notes: "Delaware is an 'unpaid balance' lien state"
    }
  },
  {
    state_code: "DC",
    state_name: "District of Columbia",
    preliminary_notice: {
      required: false,
      deadline_description: null,
      deadline_days: null,
      deadline_formula: null,
      statute: null
    },
    lien_filing: {
      deadline_description: "90 days after last furnishing",
      deadline_days: 90,
      deadline_formula: null,
      statute: "D.C. Code § 40-303.01"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: false,
      notice_of_completion_trigger: false,
      notes: ""
    }
  },
  {
    state_code: "FL",
    state_name: "Florida",
    preliminary_notice: {
      required: true,
      deadline_description: "Earlier of 45 days after first furnishing or before owner's final payment to prime",
      deadline_days: 45,
      deadline_formula: "45 days or before final payment",
      statute: "Fla. Stat. §713.06(2)"
    },
    lien_filing: {
      deadline_description: "90 days from last furnishing",
      deadline_days: 90,
      deadline_formula: null,
      statute: "Fla. Stat. §713.08(5)"
    },
    special_rules: {
      weekend_extension: true,
      holiday_extension: true,
      residential_vs_commercial: false,
      notice_of_completion_trigger: false,
      notes: "If last day falls on Saturday, Sunday, or holiday, extended to next business day"
    }
  },
  {
    state_code: "GA",
    state_name: "Georgia",
    preliminary_notice: {
      required: true,
      deadline_description: "Within 30 days of first delivering materials",
      deadline_days: 30,
      deadline_formula: null,
      statute: "Ga. Code §44-14-361.1"
    },
    lien_filing: {
      deadline_description: "90 days from last furnishing",
      deadline_days: 90,
      deadline_formula: null,
      statute: "Ga. Code §44-14-361.1"
    },
    special_rules: {
      weekend_extension: true,
      holiday_extension: true,
      residential_vs_commercial: false,
      notice_of_completion_trigger: false,
      notes: "Business day not Saturday, Sunday, or legal holiday"
    }
  },
  {
    state_code: "HI",
    state_name: "Hawaii",
    preliminary_notice: {
      required: false,
      deadline_description: null,
      deadline_days: null,
      deadline_formula: null,
      statute: null
    },
    lien_filing: {
      deadline_description: "45 days after the date of completion of the improvement",
      deadline_days: 45,
      deadline_formula: null,
      statute: "Haw. Rev. Stat. §507-43"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: false,
      notice_of_completion_trigger: true,
      notes: "SHORTEST DEADLINE IN US - Only 45 days! Notice of Completion can trigger this deadline."
    }
  },
  {
    state_code: "IA",
    state_name: "Iowa",
    preliminary_notice: {
      required: true,
      deadline_description: "30 days of first furnishing for non-residential; upon starting for owner-occupied residential",
      deadline_days: 30,
      deadline_formula: null,
      statute: "Iowa Code §572.13B"
    },
    lien_filing: {
      deadline_description: "90 days of last providing materials or labor for maximum protection",
      deadline_days: 90,
      deadline_formula: null,
      statute: "Iowa Code §572.9"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: true,
      notice_of_completion_trigger: false,
      notes: "Lien may be filed up to 2 years but only effective for unpaid amounts"
    }
  },
  {
    state_code: "ID",
    state_name: "Idaho",
    preliminary_notice: {
      required: false,
      deadline_description: null,
      deadline_days: null,
      deadline_formula: null,
      statute: null
    },
    lien_filing: {
      deadline_description: "90 days after last furnishing of labor or materials",
      deadline_days: 90,
      deadline_formula: null,
      statute: "Idaho Code § 45-507"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: false,
      notice_of_completion_trigger: false,
      notes: "Must serve copy on owner within 5 days of filing"
    }
  },
  {
    state_code: "IL",
    state_name: "Illinois",
    preliminary_notice: {
      required: true,
      deadline_description: "Within 90 days of last furnishing",
      deadline_days: 90,
      deadline_formula: null,
      statute: "770 ILCS 60/24"
    },
    lien_filing: {
      deadline_description: "Within 4 months after last item furnished",
      deadline_days: 120,
      deadline_formula: "4 months",
      statute: "770 ILCS 60/7"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: false,
      notice_of_completion_trigger: false,
      notes: "Strict 2-year enforcement deadline"
    }
  },
  {
    state_code: "IN",
    state_name: "Indiana",
    preliminary_notice: {
      required: true,
      deadline_description: "30 days (renovation) or 60 days (new construction) for residential; not required for non-residential",
      deadline_days: null,
      deadline_formula: null,
      statute: "IC 32-28-3-1(i)"
    },
    lien_filing: {
      deadline_description: "60 days residential, 90 days commercial from last furnishing (using 60-day residential default)",
      deadline_days: 60,
      deadline_formula: null,
      statute: "IC 32-28-3-3"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: true,
      notice_of_completion_trigger: false,
      notes: "Different deadlines for residential vs commercial"
    }
  },
  {
    state_code: "KS",
    state_name: "Kansas",
    preliminary_notice: {
      required: true,
      deadline_description: "Prior to filing lien for residential projects",
      deadline_days: null,
      deadline_formula: null,
      statute: "K.S.A. 60-1103a, K.S.A. 60-1103b"
    },
    lien_filing: {
      deadline_description: "3 months from last providing materials or labor",
      deadline_days: 90,
      deadline_formula: "3 months",
      statute: "K.S.A. 60-1103"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: true,
      notice_of_completion_trigger: false,
      notes: "On commercial: one-month extension possible if notice filed"
    }
  },
  {
    state_code: "KY",
    state_name: "Kentucky",
    preliminary_notice: {
      required: true,
      deadline_description: "120 days if >$1000, 75 days if ≤$1000; always 75 days for owner-occupied residential",
      deadline_days: null,
      deadline_formula: null,
      statute: "KRS §376.010(4) and (5)"
    },
    lien_filing: {
      deadline_description: "6 months from last providing materials",
      deadline_days: 180,
      deadline_formula: "6 months",
      statute: "KRS §376.080(1)"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: true,
      notice_of_completion_trigger: false,
      notes: "Preliminary deadline varies by claim amount and property type"
    }
  },
  {
    state_code: "LA",
    state_name: "Louisiana",
    preliminary_notice: {
      required: true,
      deadline_description: "within 75 days of the last day of each month of furnishing",
      deadline_days: 75,
      deadline_formula: null,
      statute: "Louisiana Revised Statutes § 9:4804(C)"
    },
    lien_filing: {
      deadline_description: "60 days from substantial completion (or 30 days from Notice of Termination if applicable)",
      deadline_days: 60,
      deadline_formula: null,
      statute: "Louisiana Revised Statutes § 9:4822"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: true,
      notice_of_completion_trigger: true,
      notes: "UNIQUE: Louisiana uses 'privilege' not 'lien'. Civil law state. Notice of Nonpayment required."
    }
  },
  {
    state_code: "ME",
    state_name: "Maine",
    preliminary_notice: {
      required: false,
      deadline_description: null,
      deadline_days: null,
      deadline_formula: null,
      statute: null
    },
    lien_filing: {
      deadline_description: "90 days after last providing materials or labor",
      deadline_days: 90,
      deadline_formula: null,
      statute: "10 M.R.S. § 3253"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: false,
      notice_of_completion_trigger: false,
      notes: "Must file enforcement action within 120 days of last furnishing"
    }
  },
  {
    state_code: "MD",
    state_name: "Maryland",
    preliminary_notice: {
      required: true,
      deadline_description: "120 days from last providing materials",
      deadline_days: 120,
      deadline_formula: null,
      statute: "Md. Code, Real Prop. §9-104(a)(1)"
    },
    lien_filing: {
      deadline_description: "180 days from last furnishing",
      deadline_days: 180,
      deadline_formula: "6 months",
      statute: "Md. Code, Real Prop. §9-105(a)"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: false,
      notice_of_completion_trigger: false,
      notes: ""
    }
  },
  {
    state_code: "MA",
    state_name: "Massachusetts",
    preliminary_notice: {
      required: true,
      deadline_description: "30 days from commencing work",
      deadline_days: 30,
      deadline_formula: null,
      statute: "M.G.L. c. 254 § 4"
    },
    lien_filing: {
      deadline_description: "Earliest of 90 days after Notice of Substantial Completion, 120 days after Notice of Termination, or 120 days after last furnished (using 90-day default)",
      deadline_days: 90,
      deadline_formula: null,
      statute: "M.G.L. c. 254 § 8"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: false,
      notice_of_completion_trigger: true,
      notes: "Multiple triggering events for deadline"
    }
  },
  {
    state_code: "MI",
    state_name: "Michigan",
    preliminary_notice: {
      required: true,
      deadline_description: "Within 20 days after first providing materials",
      deadline_days: 20,
      deadline_formula: null,
      statute: "MCL 570.1109(1)"
    },
    lien_filing: {
      deadline_description: "90 days after last providing",
      deadline_days: 90,
      deadline_formula: null,
      statute: "MCL 570.1111(1)"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: false,
      notice_of_completion_trigger: false,
      notes: ""
    }
  },
  {
    state_code: "MN",
    state_name: "Minnesota",
    preliminary_notice: {
      required: true,
      deadline_description: "within 45 days of first providing materials",
      deadline_days: 45,
      deadline_formula: null,
      statute: "Minn. Stat. §514.011, subd. 2"
    },
    lien_filing: {
      deadline_description: "120 days after last furnished",
      deadline_days: 120,
      deadline_formula: null,
      statute: "Minn. Stat. §514.08, subd. 1"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: false,
      notice_of_completion_trigger: false,
      notes: ""
    }
  },
  {
    state_code: "MS",
    state_name: "Mississippi",
    preliminary_notice: {
      required: true,
      deadline_description: "within 30 days of first furnishing labor and/or materials",
      deadline_days: 30,
      deadline_formula: null,
      statute: "Miss. Code § 85-7-407(2)"
    },
    lien_filing: {
      deadline_description: "90 days from the last date provided labor and/or materials",
      deadline_days: 90,
      deadline_formula: null,
      statute: "Miss. Code § 85-7-405(1)(b)"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: true,
      notice_of_completion_trigger: false,
      notes: "On single-family residential: pre-lien notice required at least 10 days prior to filing"
    }
  },
  {
    state_code: "MO",
    state_name: "Missouri",
    preliminary_notice: {
      required: true,
      deadline_description: "At least 10 days before filing",
      deadline_days: 10,
      deadline_formula: null,
      statute: "Mo. Rev. Stat. §429.100"
    },
    lien_filing: {
      deadline_description: "6 months after last furnishing",
      deadline_days: 180,
      deadline_formula: "6 months",
      statute: "Mo. Rev. Stat. §429.080"
    },
    special_rules: {
      weekend_extension: true,
      holiday_extension: true,
      residential_vs_commercial: false,
      notice_of_completion_trigger: false,
      notes: "If last day falls on Saturday, Sunday, or holiday, next business day"
    }
  },
  {
    state_code: "MT",
    state_name: "Montana",
    preliminary_notice: {
      required: true,
      deadline_description: "Notice of Lien Rights within 20 days of first delivering; filed within 5 days of delivery to owner",
      deadline_days: 20,
      deadline_formula: null,
      statute: "Mont. Code §71-3-536"
    },
    lien_filing: {
      deadline_description: "90 days of last providing labor or materials",
      deadline_days: 90,
      deadline_formula: null,
      statute: "Mont. Code §71-3-524"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: true,
      notice_of_completion_trigger: false,
      notes: "N/A for preliminary notice when hired directly by property owner"
    }
  },
  {
    state_code: "NC",
    state_name: "North Carolina",
    preliminary_notice: {
      required: true,
      deadline_description: "Within 15 days from first furnishing",
      deadline_days: 15,
      deadline_formula: null,
      statute: "G.S. 44A-11.2(l)(1)"
    },
    lien_filing: {
      deadline_description: "Within 120 days from last furnishing",
      deadline_days: 120,
      deadline_formula: null,
      statute: "G.S. 44A-12(b)"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: false,
      notice_of_completion_trigger: false,
      notes: ""
    }
  },
  {
    state_code: "ND",
    state_name: "North Dakota",
    preliminary_notice: {
      required: true,
      deadline_description: "Notice of Intent to Lien 10 days before filing lien",
      deadline_days: 10,
      deadline_formula: null,
      statute: "ND Cent. Code §35-27-02"
    },
    lien_filing: {
      deadline_description: "90 days from last delivery of labor or materials",
      deadline_days: 90,
      deadline_formula: null,
      statute: "ND Cent. Code §35-27-13"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: false,
      notice_of_completion_trigger: false,
      notes: "Late lien may be filed within 3 years but limited validity"
    }
  },
  {
    state_code: "NE",
    state_name: "Nebraska",
    preliminary_notice: {
      required: false,
      deadline_description: null,
      deadline_days: null,
      deadline_formula: null,
      statute: null
    },
    lien_filing: {
      deadline_description: "120 days of last providing labor or materials",
      deadline_days: 120,
      deadline_formula: null,
      statute: "Neb. Rev. Stat. §52-137"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: false,
      notice_of_completion_trigger: false,
      notes: "Must send stamped copy to property owner within 10 days of recording"
    }
  },
  {
    state_code: "NH",
    state_name: "New Hampshire",
    preliminary_notice: {
      required: true,
      deadline_description: "Best Practice: Notice of lien rights prior to providing labor/materials. Written account every 30 days.",
      deadline_days: null,
      deadline_formula: null,
      statute: "N.H. Rev. Stat. § 447:5-8"
    },
    lien_filing: {
      deadline_description: "120 days of last providing labor or materials",
      deadline_days: 120,
      deadline_formula: null,
      statute: "N.H. Rev. Stat. § 447:9"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: false,
      notice_of_completion_trigger: false,
      notes: "Lien not recorded prior to enforcement action; file Ex Parte Petition to Secure Mechanics Lien"
    }
  },
  {
    state_code: "NJ",
    state_name: "New Jersey",
    preliminary_notice: {
      required: true,
      deadline_description: "60 days for residential; 90 days for non-residential",
      deadline_days: null,
      deadline_formula: null,
      statute: "N.J.S.A. 2A:44A-20"
    },
    lien_filing: {
      deadline_description: "90 days non-residential, 120 days residential from last providing (using 90-day non-residential default)",
      deadline_days: 90,
      deadline_formula: null,
      statute: "N.J.S.A. 2A:44A-6"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: true,
      notice_of_completion_trigger: false,
      notes: "Different deadlines for residential vs commercial"
    }
  },
  {
    state_code: "NM",
    state_name: "New Mexico",
    preliminary_notice: {
      required: true,
      deadline_description: "within 60 days after initially furnishing work or materials",
      deadline_days: 60,
      deadline_formula: null,
      statute: "NM Stat. §48-2-2.1"
    },
    lien_filing: {
      deadline_description: "90 days after project completion; 120 days if supplying directly to property owner",
      deadline_days: 90,
      deadline_formula: null,
      statute: "NM Stat. §48-2-6"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: true,
      notice_of_completion_trigger: false,
      notes: "Not required if claim <$5000 or on residential with <4 dwellings"
    }
  },
  {
    state_code: "NV",
    state_name: "Nevada",
    preliminary_notice: {
      required: true,
      deadline_description: "Within 31 days of first furnishing",
      deadline_days: 31,
      deadline_formula: null,
      statute: "NRS 108.245"
    },
    lien_filing: {
      deadline_description: "90 days after last furnishing or completion",
      deadline_days: 90,
      deadline_formula: null,
      statute: "N.R.S. §108.226"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: true,
      notice_of_completion_trigger: true,
      notes: "If Notice of Completion served: 40 days. For residential: Notice of Intent 15 days before recording"
    }
  },
  {
    state_code: "NY",
    state_name: "New York",
    preliminary_notice: {
      required: false,
      deadline_description: null,
      deadline_days: null,
      deadline_formula: null,
      statute: null
    },
    lien_filing: {
      deadline_description: "8 months from last furnishing; 4 months for single-family residential",
      deadline_days: 240,
      deadline_formula: "8 months or 4 months",
      statute: "NY Lien Law §10"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: true,
      notice_of_completion_trigger: false,
      notes: "Different deadlines for residential (4 months) vs commercial (8 months)"
    }
  },
  {
    state_code: "OH",
    state_name: "Ohio",
    preliminary_notice: {
      required: true,
      deadline_description: "21 days from first furnishing",
      deadline_days: 21,
      deadline_formula: null,
      statute: "O.R.C. §1311.05"
    },
    lien_filing: {
      deadline_description: "75 days non-residential; 60 days residential from last furnishing (using 60-day residential default)",
      deadline_days: 60,
      deadline_formula: null,
      statute: "O.R.C. §1311.06(B)"
    },
    special_rules: {
      weekend_extension: true,
      holiday_extension: true,
      residential_vs_commercial: true,
      notice_of_completion_trigger: false,
      notes: "If last date falls on Saturday, Sunday, or legal holiday, next business day. Preliminary only required if Notice of Commencement filed."
    }
  },
  {
    state_code: "OK",
    state_name: "Oklahoma",
    preliminary_notice: {
      required: true,
      deadline_description: "within 75 days of last delivering if owner-occupied or claim ≥$10,000",
      deadline_days: 75,
      deadline_formula: null,
      statute: "Okla. Stat. tit. 42 §142.6"
    },
    lien_filing: {
      deadline_description: "within 90 days from last furnished",
      deadline_days: 90,
      deadline_formula: null,
      statute: "Okla. Stat. tit. 42 §143"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: true,
      notice_of_completion_trigger: false,
      notes: "Not required for residential ≤4 units none occupied by owner, or if claim <$10,000"
    }
  },
  {
    state_code: "OR",
    state_name: "Oregon",
    preliminary_notice: {
      required: true,
      deadline_description: "Within 8 days of first furnishing",
      deadline_days: 8,
      deadline_formula: null,
      statute: "ORS § 87.021"
    },
    lien_filing: {
      deadline_description: "75 days after last furnishing or completion, whichever earlier",
      deadline_days: 75,
      deadline_formula: null,
      statute: "ORS § 87.035"
    },
    special_rules: {
      weekend_extension: true,
      holiday_extension: true,
      residential_vs_commercial: false,
      notice_of_completion_trigger: false,
      notes: "CRITICAL: Preliminary deadline is 8 BUSINESS DAYS (excludes Saturdays, Sundays, holidays)"
    }
  },
  {
    state_code: "PA",
    state_name: "Pennsylvania",
    preliminary_notice: {
      required: false,
      deadline_description: null,
      deadline_days: null,
      deadline_formula: null,
      statute: null
    },
    lien_filing: {
      deadline_description: "6 months after last materials furnished",
      deadline_days: 180,
      deadline_formula: "6 months",
      statute: "49 P.S. § 1502(a)"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: false,
      notice_of_completion_trigger: false,
      notes: "Subcontractors must give 30-day pre-lien notice"
    }
  },
  {
    state_code: "RI",
    state_name: "Rhode Island",
    preliminary_notice: {
      required: true,
      deadline_description: "Notice of Intent within same 200-day period as lien",
      deadline_days: 200,
      deadline_formula: null,
      statute: "R.I. Gen. Laws § 34-28-4"
    },
    lien_filing: {
      deadline_description: "200 days after last labor or materials furnished",
      deadline_days: 200,
      deadline_formula: null,
      statute: "R.I. Gen. Laws § 34-28-4"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: false,
      notice_of_completion_trigger: false,
      notes: ""
    }
  },
  {
    state_code: "SC",
    state_name: "South Carolina",
    preliminary_notice: {
      required: false,
      deadline_description: null,
      deadline_days: null,
      deadline_formula: null,
      statute: "S.C. Code §29-5-10"
    },
    lien_filing: {
      deadline_description: "90 days after last materials furnished",
      deadline_days: 90,
      deadline_formula: null,
      statute: "S.C. Code §29-5-90"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: false,
      notice_of_completion_trigger: false,
      notes: ""
    }
  },
  {
    state_code: "SD",
    state_name: "South Dakota",
    preliminary_notice: {
      required: true,
      deadline_description: "If Notice of Commencement filed: Preliminary Notice within 60 days of last furnishing",
      deadline_days: 60,
      deadline_formula: null,
      statute: "SDCL § 44-9-53"
    },
    lien_filing: {
      deadline_description: "120 days after last labor or materials furnished",
      deadline_days: 120,
      deadline_formula: null,
      statute: "SDCL § 44-9-15"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: false,
      notice_of_completion_trigger: false,
      notes: "If no Notice of Commencement filed, no preliminary notice required"
    }
  },
  {
    state_code: "TN",
    state_name: "Tennessee",
    preliminary_notice: {
      required: true,
      deadline_description: "Within 90 days of the last day of the month materials provided",
      deadline_days: null,
      deadline_formula: "90 days from end of month",
      statute: "§ 66-11-145"
    },
    lien_filing: {
      deadline_description: "90 days after completion or abandonment",
      deadline_days: 90,
      deadline_formula: null,
      statute: "T.C.A. § 66-11-112(a)"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: true,
      notice_of_completion_trigger: true,
      notes: "If Notice of Completion filed on commercial: 30 days. No liens on certain residential."
    }
  },
  {
    state_code: "TX",
    state_name: "Texas",
    preliminary_notice: {
      required: true,
      deadline_description: "Non-residential: 15th of 3rd month; Residential: 15th of 2nd month",
      deadline_days: null,
      deadline_formula: "3rd month + 15 days (non-res); 2nd month + 15 days (res)",
      statute: "Texas Property Code § 53.056"
    },
    lien_filing: {
      deadline_description: "Non-residential: 15th of 4th month; Residential: 15th of 3rd month (105-day commercial default if formula unavailable)",
      deadline_days: 105,
      deadline_formula: "4th month + 15 days (non-res); 3rd month + 15 days (res)",
      statute: "Texas Property Code § 53.052"
    },
    special_rules: {
      weekend_extension: true,
      holiday_extension: true,
      residential_vs_commercial: true,
      notice_of_completion_trigger: false,
      notes: "CRITICAL: Uses month + day formula, NOT flat day count. If 15th falls on weekend or federal holiday, extends to next business day."
    }
  },
  {
    state_code: "UT",
    state_name: "Utah",
    preliminary_notice: {
      required: true,
      deadline_description: "Within 20 days after commencement or delivery",
      deadline_days: 20,
      deadline_formula: null,
      statute: "Utah Code § 38-1a-501(1)(a)"
    },
    lien_filing: {
      deadline_description: "180 days after final completion if no notice; 90 days after notice of completion (max 180 days)",
      deadline_days: 180,
      deadline_formula: null,
      statute: "Utah Code § 38-1a-502(1)(a)"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: false,
      notice_of_completion_trigger: true,
      notes: "Late preliminary effective 5 days after filing"
    }
  },
  {
    state_code: "VA",
    state_name: "Virginia",
    preliminary_notice: {
      required: true,
      deadline_description: "30 days from last delivery or from permit issuance",
      deadline_days: 30,
      deadline_formula: null,
      statute: "§ 43-4.01"
    },
    lien_filing: {
      deadline_description: "90 days from last day of month materials last furnished",
      deadline_days: 90,
      deadline_formula: null,
      statute: "§ 43-4"
    },
    special_rules: {
      weekend_extension: true,
      holiday_extension: false,
      residential_vs_commercial: false,
      notice_of_completion_trigger: false,
      notes: "If 90th day on weekend, next business day. Lien limited to 150 days preceding last furnishing."
    }
  },
  {
    state_code: "VT",
    state_name: "Vermont",
    preliminary_notice: {
      required: false,
      deadline_description: null,
      deadline_days: null,
      deadline_formula: null,
      statute: null
    },
    lien_filing: {
      deadline_description: "180 days from when payment became due for last materials or labor",
      deadline_days: 180,
      deadline_formula: null,
      statute: "9 V.S.A. § 1921(c)"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: false,
      notice_of_completion_trigger: false,
      notes: "Unclear if from date payment due to claimant or to last party on project"
    }
  },
  {
    state_code: "WA",
    state_name: "Washington",
    preliminary_notice: {
      required: true,
      deadline_description: "Within 60 days from first delivering",
      deadline_days: 60,
      deadline_formula: null,
      statute: "RCW 60.04.031"
    },
    lien_filing: {
      deadline_description: "90 days from last furnished",
      deadline_days: 90,
      deadline_formula: null,
      statute: "RCW 60.04.091"
    },
    special_rules: {
      weekend_extension: true,
      holiday_extension: true,
      residential_vs_commercial: false,
      notice_of_completion_trigger: false,
      notes: "CRITICAL: Preliminary notice required for SUPPLIERS within 60 days. Not required for contractors. If deadline on weekend or holiday, extends to next business day."
    }
  },
  {
    state_code: "WI",
    state_name: "Wisconsin",
    preliminary_notice: {
      required: true,
      deadline_description: "60 days after first providing to owner",
      deadline_days: 60,
      deadline_formula: null,
      statute: "Wis. Stat. § 779.02(2)(b)"
    },
    lien_filing: {
      deadline_description: "6 months from last providing",
      deadline_days: 180,
      deadline_formula: "6 months",
      statute: "Wis. Stat. § 779.06(1)"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: false,
      notice_of_completion_trigger: false,
      notes: "Notice of intent 30 days before lien. Must serve lien on owner within 30 days of filing."
    }
  },
  {
    state_code: "WV",
    state_name: "West Virginia",
    preliminary_notice: {
      required: false,
      deadline_description: null,
      deadline_days: null,
      deadline_formula: null,
      statute: null
    },
    lien_filing: {
      deadline_description: "100 days from last providing labor or materials",
      deadline_days: 100,
      deadline_formula: null,
      statute: "W. Va. Code §§38-2-8 through 38-2-13"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: true,
      residential_vs_commercial: false,
      notice_of_completion_trigger: false,
      notes: "If due date falls on a holiday, notice is due on the day prior"
    }
  },
  {
    state_code: "WY",
    state_name: "Wyoming",
    preliminary_notice: {
      required: true,
      deadline_description: "within 30 days after first providing labor or materials",
      deadline_days: 30,
      deadline_formula: null,
      statute: "W.S. 29-2-112"
    },
    lien_filing: {
      deadline_description: "120 days from last delivering labor or materials",
      deadline_days: 120,
      deadline_formula: null,
      statute: "W.S. 29-2-106(a)"
    },
    special_rules: {
      weekend_extension: false,
      holiday_extension: false,
      residential_vs_commercial: false,
      notice_of_completion_trigger: false,
      notes: "Notice of Intent to lien required 20 days prior to filing lien"
    }
  }
];
