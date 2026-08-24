# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

from app.tools import report_barred_run, run_b_gate, run_debate_case, summarize_artifacts


MODEL = "gemini-3.6-flash"


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are BARRED-Fleet, an adapter over the BARRED security-evidence harness. "
        "Use deterministic tools for artifact facts. Do not invent missing metrics, "
        "and do not describe cassette replay as provider-side cache telemetry."
    ),
    tools=[summarize_artifacts, run_b_gate, report_barred_run, run_debate_case],
)

app = App(
    root_agent=root_agent,
    name="app",
)
