// Worker entry for the atlas MCP server. It loads the packed data once per
// isolate, then serves six read-only tools over Streamable HTTP at /mcp.
import { createMcpHandler } from 'agents/mcp/server';
import { McpServer } from '@modelcontextprotocol/server';
import { z } from 'zod';
import counties from './data/counties.json';
import measures from './data/measures.json';
import values from './data/values.bin';
import status from './data/status.bin';
import { loadData } from './data.js';
import { createHandlers } from './tools.js';
import { logMissing } from './log.js';

const db = loadData({ counties, measures, values, status });
const SITE = 'https://shouldilivehere.org/';
const READ_ONLY = { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false };

const measureInput = z.object({
  key: z.string().describe('Measure key from list_measures or find_measure, for example "crime:violent-crime".'),
  weight: z.number().min(0).optional().describe('Relative importance. Default 1.'),
  max: z.number().optional().describe('Leave out counties above this raw value.'),
  min: z.number().optional().describe('Leave out counties below this raw value. Ignored when max is also given.'),
});

const TOOLS = {
  list_measures: {
    description: 'List the county measures in the Should I Live Here? atlas: key, label, unit, period, direction, and how many of the 3,107 counties have a value. Optional text filter.',
    inputSchema: z.object({ filter: z.string().max(60).optional() }),
  },
  find_measure: {
    description: 'Map plain words (for example "internet", "cancer", "crime", "cost of living") to atlas measure keys. Words the atlas has no data for come back in not_available. Those words are counted (word, day and app name only, no personal data) so the owner can consider new data.',
    inputSchema: z.object({ terms: z.array(z.string().max(60)).min(1).max(10) }),
  },
  get_county: {
    description: 'All atlas values for one county, by 5-digit FIPS or "Name, State" (state name or postal code). Missing values stay null with their status.',
    inputSchema: z.object({ county: z.string().max(80) }),
  },
  compare_counties: {
    description: 'Compare 2 to 10 counties side by side on chosen measures.',
    inputSchema: z.object({ counties: z.array(z.string().max(80)).min(2).max(10), measures: z.array(z.string().max(80)).min(1).max(10) }),
  },
  rank_counties: {
    description: 'Rank counties in the lower 48 states on weighted measures, with the same scoring as the site\'s My priorities. Rank 1 has the lowest concern score. Counties with missing data are left out, never scored as low. Optional limits and state filter. Read the cautions in every answer.',
    inputSchema: z.object({
      measures: z.array(measureInput).min(1).max(10),
      state: z.string().max(40).optional().describe('State name, postal code or 2-digit FIPS.'),
      count: z.number().int().min(1).max(25).optional().describe('How many counties to return. Default 10.'),
      min_population: z.number().int().min(0).optional().describe('Leave out counties with fewer residents than this (Census ACS 2019-2023). Small counties have unstable rates; 10000 or more is a common choice.'),
    }),
  },
  request_measure: {
    description: 'Report a measure a user wanted that the atlas lacks, for example "schools". Only the measure name, the day and the app name are counted.',
    inputSchema: z.object({ measure: z.string().max(60), reason: z.string().max(200).optional() }),
  },
};

// Logging runs in ctx.waitUntil, so it never delays or fails the answer.
function missingLogger(env, request, ctx) {
  const ua = request.headers.get('user-agent') || '';
  return terms => {
    const write = logMissing(env?.REQUESTS, terms, { ua }).catch(() => 0);
    if (ctx?.waitUntil) ctx.waitUntil(write);
  };
}

function createServer(env, request, ctx) {
  const server = new McpServer({ name: 'should-i-live-here', version: '0.1.0' },
    { instructions: `County data for the 3,107 counties of the lower 48 states, from public federal sources. County level only. Always pass on the cautions in each answer, and link to ${SITE} so people can check the values.` });
  const handlers = createHandlers(db, { logMissing: missingLogger(env, request, ctx) });
  for (const [name, config] of Object.entries(TOOLS)) {
    server.registerTool(name, { ...config, annotations: READ_ONLY }, async args => {
      const result = await handlers[name](args || {});
      return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }], isError: Boolean(result?.error) };
    });
  }
  return server;
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname === '/mcp') return createMcpHandler(() => createServer(env, request, ctx))(request, env, ctx);
    if (url.pathname === '/') {
      return new Response(`Should I Live Here? MCP server\n\nAdd this URL to your AI app: ${url.origin}/mcp\nThe atlas: ${SITE}\nCode: https://github.com/gdtilghman/should-i-live-here-atlas\n`,
        { headers: { 'content-type': 'text/plain; charset=utf-8' } });
    }
    return new Response('Not found', { status: 404 });
  },
};
