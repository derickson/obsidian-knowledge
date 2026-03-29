right now the mcp server has some instructions on the
  layout of my obsidian vault that are specific to the
  AgentKnowledge vault and not relevant to other vaults.
  Also the button on the ui to go to the daily note or
  create it really is only going to work on the
  AgentKnowledge vault.  I want the instruction for the
  layout of the vault to be moved into the vault
  configuration file and be editable with a larger
  scrolling text entry in the Settings of the UI.  The
  button for daily note needs to be dynamic for the vault
  we are in.  you can relocate the hard coded vault
  instructions from the MCP instructions for
  AgentKnowledge but have it start blank for the other
  existing vaults or new vaults being made.  The editor
  for the vault description should have a button for
  `re-generate instruction template` (with a check to
  makes sure as it is destructive) that will scan folder
  layout of the vault down to 2 levels of folders and
  look at the first 10 filenames per folder to infer an
  instruction on the layout of the vault.  All
  re-generated instructions should have required notes
  for time stamp etc.

  We want the mcp to have new tools for "getVaultLayout"
  parameterized by vault so that agents can understand
  the vault layout before editing.  The MCP instructions
  should be adjusted to explain this.
