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
  heatAllTime: (total: number) => string;
  cumulativeTitle: string;
  cumulativeUnit: string;
  recentShowing: (shown: number, total: number) => string;
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
  // Batch 1 — email verification
  verifyEmailTitle: string;
  verifyEmailText: (email: string) => string;
  verifyCodeLabel: string;
  verifyCodePlaceholder: string;
  verifyEmailBtn: string;
  resendCode: string;
  codeResent: string;
  // Batch 1 — TOTP 2FA
  totpTitle: string;
  totpText: string;
  totpCodeLabel: string;
  totpUseBackup: string;
  totpVerifyBtn: string;
  totpSetupTitle: string;
  totpSetupText: string;
  totpScanQr: string;
  totpManualSecret: string;
  totpEnableBtn: string;
  totpEnabled: string;
  totpDisabled: string;
  totpDisableBtn: string;
  totpBackupTitle: string;
  totpBackupText: string;
  totpBackupSaved: string;
  totpRegenerate: string;
  totpStatusOn: string;
  totpStatusOff: string;
  totpRemaining: (n: number) => string;
  // Batch 1 — handle verification
  handleStep1Text: string;
  handleTokenLabel: string;
  handleTokenHint: string;
  handleConfirmBtn: string;
  handleVerified: string;
  handlePendingText: (handle: string) => string;
  handleStartAgain: string;
  copyToken: string;
  tokenCopied: string;
  // Batch 1 — security
  securityTitle: string;
  emailVerified: string;
  emailNotVerified: string;
  passwordConfirmLabel: string;
  deletePasswordHint: string;
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
  // Phase 3 — ML solvability prediction
  predSolvable: (pct: number) => string;
  predTitle: string;
  predSettingsTitle: string;
  predModel: string;
  predTrainedOn: string;
  predData: string;
  predRows: (rows: number, solved: number) => string;
  predTestAuc: string;
  predBaselineAuc: string;
  predFeatures: string;
  predBias: string;
  predTrainedLabelDemo: string;
  predTrainedLabelMixed: string;
  predTrainedLabelReal: string;
  predNotTrained: string;
  predNotShipped: string;
  predRetrain: string;
  predRetrained: string;
  predRetraining: string;
  predRetrainFailed: string;
  predPlatformTitle: string;
  predPlatformNote: string;
  // toasts (Sonner)
  toastSynced: string;
  toastSavedLater: string;
  toastNotInterested: string;
  toastUndone: string;
  toastReviewed: (result: string) => string;
  toastCopied: string;
  undo: string;
  // command palette ("/" search)
  palettePlaceholder: string;
  palettePages: string;
  paletteActions: string;
  paletteProblems: string;
  paletteNoResults: string;
  paletteSearchHint: string;
  paletteGoDemo: string;
  paletteGoHome: string;
  paletteToggleTheme: string;
  paletteSwitchLanguage: string;
  paletteNavigate: string;
  paletteOpen: string;
  paletteClose: string;
  // practice filters + saved views
  filterRatingBand: string;
  clearFilters: (n: number) => string;
  savedViews: string;
  saveView: string;
  saveViewName: string;
  noSavedViews: string;
  viewSaved: string;
  deleteView: string;
  // topic goal rings
  topicGoals: string;
  goalTarget: (pct: number) => string;
  goalPractice: (tag: string) => string;
  goalAttempted: (n: number) => string;
  goalWeak: string;
  goalOnTrack: string;
  // chart ranges
  rangeDays: string;
  rangeWeeks: string;
  rangeMonths: string;
  activityDaily: string;
  activityWeekly: string;
  heatWeekTooltip: (date: string, count: number) => string;
  // copy training plan
  copyPlan: string;
  copied: string;
  // Phase 2 nav
  navAnalytics: string;
  navCalendar: string;
  navWeekly: string;
  navSettings: string;
  // Phase 2 analytics
  analyticsTitle: string;
  statPeakRating: string;
  statLongestStreak: string;
  difficultyDist: string;
  difficultySuccess: string;
  milestonesTitle: string;
  milestoneUnlocked: string;
  milestoneLocked: (n: number) => string;
  contestsTitle: string;
  contestSolvedDay: (solved: number, attempted: number) => string;
  contestWeakTags: string;
  contestFirst: string;
  noContests: string;
  noContestsHint: string;
  // Phase 2 calendar
  calendarTitle: string;
  calendarToday: string;
  calendarSelectDay: string;
  calendarNoData: string;
  calendarSolved: (n: number) => string;
  calendarAttempted: (n: number) => string;
  calendarStreakDay: string;
  daySubmissions: string;
  // Phase 2 weekly report
  weeklyTitle: string;
  weekSolved: string;
  weekAttempted: string;
  weekAcceptance: string;
  weekVsLast: (delta: number) => string;
  weekFocus: string;
  weekFocusEmpty: string;
  weekTopTags: string;
  weakMovement: string;
  movementNoData: string;
  weeklyArchive: string;
  weeklyExport: string;
  weeklyExported: string;
  // Phase 2 problem detail
  problemAttempts: string;
  problemSolved: string;
  problemNotSolved: string;
  problemFirstAttempt: string;
  problemLastAttempt: string;
  problemSubmissions: string;
  problemNotes: string;
  notePlaceholder: string;
  noteSave: string;
  noteSaved: string;
  notePreview: string;
  noteEdit: string;
  noteEmpty: string;
  revisionStatus: string;
  revisionNoRevision: string;
  // Phase 2 settings
  settingsTitle: string;
  settingsAccount: string;
  settingsHandle: string;
  settingsRank: string;
  settingsGoal: string;
  settingsGoalHint: string;
  settingsGoalSave: string;
  settingsGoalSaved: string;
  settingsGoalProgress: (solved: number, target: number) => string;
  settingsDisconnect: string;
  settingsDisconnectConfirm: string;
  settingsDisconnected: string;
  settingsExport: string;
  settingsExportHint: string;
  settingsExported: string;
  settingsDelete: string;
  settingsDeleteConfirm: string;
  settingsDeleteHint: string;
  settingsDemoNote: string;
  settingsDemoAccount: string;
  settingsAppearance: string;
  // Phase 2 dashboard additions
  weeklyGoal: string;
  weeklyGoalDone: string;
  viewAnalytics: string;
  viewWeeklyReport: string;
  insightsTitle: string;
}
