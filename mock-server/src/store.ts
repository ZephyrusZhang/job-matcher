export const store = {
  favorites: new Set<string>(),
  resume: null as any,
  reports: new Map<string, any>(),
  chatHistory: new Map<string, any[]>(),
  settings: { display_density: 'comfortable' as string, language: 'zh' as string },
};
