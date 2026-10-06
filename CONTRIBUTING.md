# Contributing to AI-Assisted DMX Web Controller

Thank you for contributing to the DMX Web Controller! We welcome bug reports, hardware driver contributions, new fixture profiles, and improvements to the AI prompting engine.

## Code Standards
1. **Python 3.9+ Compatibility**: Code should run on Python 3.9 through 3.12 without deprecation warnings.
2. **Modular Architecture**:
   - `database/`: Schema migrations and data access repositories.
   - `engine/`: High-performance, thread-safe in-memory mixer, serial drivers, and script execution sandbox.
   - `ai/`: Gemini API integration, AST safety validator, self-healing telemetry, and interactive wizards.
3. **No External Build Steps**: Frontend is written in clean, modern vanilla JavaScript and CSS to allow immediate installation without Node.js or NPM build chains.
4. **Safety First**: Any modifications to the procedural show execution model must pass the `ScriptASTValidator` test suite.

## Development Workflow
1. Fork the repository and create your feature branch:
   ```bash
   git checkout -b feature/my-cool-feature
   ```
2. Set up your virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Run the unit test suite:
   ```bash
   python3 -m unittest discover tests -v
   ```
4. Commit your changes and submit a pull request!
