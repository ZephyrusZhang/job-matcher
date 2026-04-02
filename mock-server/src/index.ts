import express from 'express';
import cors from 'cors';

import companiesRouter from './routes/companies.js';
import jobsRouter from './routes/jobs.js';
import favoritesRouter from './routes/favorites.js';
import resumeRouter from './routes/resume.js';
import matchRouter from './routes/match.js';
import compareRouter from './routes/compare.js';
import chatRouter from './routes/chat.js';
import crawlRouter from './routes/crawl.js';
import settingsRouter from './routes/settings.js';

const app = express();
const PORT = 3001;

// Middleware
app.use(cors());
app.use(express.json());

// Routes
app.use('/api', companiesRouter);
app.use('/api', jobsRouter);
app.use('/api', favoritesRouter);
app.use('/api', resumeRouter);
app.use('/api', matchRouter);
app.use('/api', compareRouter);
app.use('/api', chatRouter);
app.use('/api', crawlRouter);
app.use('/api', settingsRouter);

app.listen(PORT, () => {
  console.log(`Mock server running at http://localhost:${PORT}`);
});
