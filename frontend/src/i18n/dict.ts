/* i18n dictionary types. en.ts / bn.ts implement Dict; the UI only ever
   reads strings through useLanguage().t — no hardcoded user-facing text
   lives in components. */

export type Locale = 'en' | 'bn';

/** Structured "why" from the backend (services.recommend / seed.why_for).
    The frontend renders the sentence in the active locale. */
export interface WhyInfo {
  kind: 'weak_acceptance' | 'weak_wrong' | 'near_rating';
  tag?: string;
  acceptance?: number;
  avg_wrong_attempts?: number;
  problem_rating: number;
  user_rating: number;
  demo_out_of_band?: boolean;
}

export interface Dict {
  // nav / shell
  navDashboard: string;
  navPractice: string;
  navRevision: string;
  demoMode: string;
  logOut: string;
  cfHandleLine: (handle: string) => string;
  sidebarNote1: string;
  sidebarNote2: string;
  switchToLight: string;
  switchToDark: string;
  switchLanguage: string;
  // sync chip
  syncingSubmissions: (n: number) => string;
  syncing: string;
  syncFailed: (error: string | null) => string;
  retry: string;
  notSyncedYet: string;
  syncedAgo: (ago: string) => string;
  syncNow: string;
  // time ago
  justNow: string;
  minAgo: (n: number) => string;
  hoursAgo: (n: number) => string;
  daysAgo: (n: number) => string;
  never: string;
  // banners
  demoBanner: string;
  createAccount: string;
  coldStart: string;
  // landing
  landingBadge: string;
  landingTitle: string;
  landingSub: string;
  tryDemoNoLogin: string;
  tryDemo: string;
  login: string;
  feature1Title: string;
  feature1Text: string;
  feature2Title: string;
  feature2Text: string;
  feature3Title: string;
  feature3Text: string;
  howItWorks: string;
  step1Title: string;
  step1Text: string;
  step2Title: string;
  step2Text: string;
  step3Title: string;
  step3Text: string;
  builtWith: (a: string, b: string, c: string) => string;
  ctaTitle: string;
  footerNote: string;
  previewCaption: string;
  previewRating: string;
  previewSolved: string;
  previewStreak: string;
  previewStreakValue: string;
  previewDue: string;
  previewTodayPlan: string;
  previewRatingTrend: string;
  // dashboard
  dashboard: string;
  noSyncYet: string;
  connectHandleHint: string;
  statRating: string;
  statSolved: string;
  statStreak: string;
  statRevisionDue: string;
  subSolved: string;
  subStreak: (n: number) => string;
  subRevisions: string;
  reviseLabel: string;
  lastContest: string;
  ratingHistory: string;
  todaysPlan: string;
  nothingPlanned: string;
  topicStrength: string;
  weakRightNow: (tags: string) => string;
  dailyActivity: string;
  recentSubmissions: string;
  demoFootnote: string;
  cfNoResponse: string;
  cfRetryAuto: string;
  cfRetryAutoShort: string;
  chartNotEnough: string;
  chartNoTags: string;
  chartNoActivity: string;
  heatLess: string;
  heatMore: string;
  notEnoughContests: string;
  noTagData: string;
  noActivityYet: string;
  heatTooltip: (date: string, count: number) => string;
  noSubmissionsYet: string;
  verdictAccepted: string;
  thProblem: string;
  thVerdict: string;
  thLanguage: string;
  thTime: string;
  // practice
  practice: string;
  filterTag: string;
  filterAllTags: string;
  filterMinRating: string;
  filterMaxRating: string;
  filterHideSolved: string;
  filterShowAll: (n: number) => string;
  filterShowFewer: string;
  noProblemsMatch: string;
  noProblemsMatchHint: string;
  demoPracticeNote: string;
  openOnCf: string;
  later: string;
  savedForLater: string;
  notInterested: string;
  disabledInDemo: string;
  // revision
  revision: string;
  tabDue: string;
  tabUpcoming: string;
  tabDone: string;
  noRevisionsDue: string;
  allCaughtUp: string;
  nothingHere: string;
  upcomingHint: string;
  doneHint: string;
  lastAttempt: (wrong: number, interval: number) => string;
  lastReview: (result: string) => string;
  reviewedAs: (result: string, next: string) => string;
  reviewedNext1Day: string;
  reviewedNextLonger: string;
  reviewAgain: string;
  reviewHard: string;
  reviewGood: string;
  reviewEasy: string;
  hintAgain: string;
  hintHard: string;
  hintGood: string;
  hintEasy: string;
  rateKeysHint: string;
  previous: string;
  next: string;
  comingUp: string;
  demoRevisionNote: string;
  // auth
  welcomeBack: string;
  createAccountTitle: string;
  loginSub: string;
  registerSub: string;
  email: string;
  password: string;
  passwordPlaceholder: string;
  logIn: string;
  createAccountBtn: string;
  noAccountYet: string;
  haveAccount: string;
  accountCreated: string;
  somethingWrong: string;
  connectHandleTitle: string;
  connectHandleText: string;
  handlePlaceholder: string;
  verifyConnect: string;
  handleVerifyError: string;
  // 404
  notFoundTitle: string;
  notFoundText: string;
  goHome: string;
  // "why" sentences (functions so each locale can order words its own way)
  whyWeakAcceptance: (tag: string, pct: number, rating: number) => string;
  whyWeakWrong: (tag: string, avg: number, rating: number) => string;
  whyNearRating: (userRating: number, rating: number) => string;
  whyDemoOutOfBand: string;
  recScore: (s: number) => string;
}
