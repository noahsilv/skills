# MCP server projects

Alongside the skills, Noah built MCP (Model Context Protocol) servers that let AI assistants query data services and call another model. These projects cover financial-data retrieval and the integration work needed to use external services from an assistant.

| Project | What it does | Implementation details |
| --- | --- | --- |
| Macro-data connector bundle | Retrieves economic series and development-finance data from FRED, IMF, OECD and World Bank services, including IFC project data. | OECD dataset discovery and dimension lookup; World Bank Data360 pagination, metadata and source information on each observation. Source code remains private. |
| IATI data server | Queries published development activities, transactions and budgets through the IATI Datastore. | Publisher and country filters, paginated queries and activity-identifier checks. Source code remains private. |
| [Ultramarine model connector](https://github.com/noahsilv/ultramarine1) | Sends bounded text tasks to Ultramarine and returns candidate answers or Python proposals for host review. | Input and output limits, explicit failure responses and a separation between proposing code and executing it. The server does not execute the proposed code. |
| [Plaud recording bridge](https://github.com/noahsilv/plaudcli) | Gives an assistant read-only access to an authorized user's recordings, transcripts and notes. | OAuth token refresh, pagination and structured errors. An independent integration with Plaud's service, not the official Plaud product. |

The public repositories provide code and test suites for inspection. These descriptions were checked against source and documentation; live services were not retested for this portfolio update. Server tests are separate from this repository's skill tests. Private source code, credentials and account data are not included here.

The portfolio also includes a [runnable MCP example](../skills/mcp-api-integration/README.md) with a synthetic service. Its local tests exercise the protocol and failure handling.
