```
###############################################################################
# VALIDATION LOGIC (GUI interactions removed)
# Inputs follow the generic data model (datamodel.xlsx) and array semantics.
# - AccountNumber: string  (customer/account reference)
# - ServicePoints: array of ServicePoint items (0..n), each with:
#     Enabled?: boolean
#     PostalCode: string
#     Identifier?: string
#     Type?: string
#     City?: string
#
# External validation sources:
# - Address Directory (read-only): provides existence checks and classifications.
###############################################################################

CONSTANT VALID_CLASSIFICATIONS = {"FOO", "BAR"}

FUNCTION ValidateServicePoints(AccountNumber, ServicePoints):
    results = []

    FOR EACH sp IN ServicePoints:
        # Skip items explicitly disabled or not provided
        IF sp.Enabled IS DEFINED AND sp.Enabled == FALSE:
            CONTINUE

        # --- Rule: PostalCode is mandatory for any validation ---
        IF NOT Present(sp.PostalCode):
            results.APPEND(Result(sp, status="ESCALATE", reason="MissingPostalCode"))
            CONTINUE

        # --- Case A: PostalCode + Identifier provided ---
        IF Present(sp.Identifier):
            # Must exist as a valid combination for the customer
            IF ExistsCombination(AccountNumber, sp.PostalCode, sp.Identifier):   # from Address Directory
                results.APPEND(Result(sp, status="VALID"))
            ELSE:
                results.APPEND(Result(sp, status="ESCALATE", reason="CombinationNotFound"))
            CONTINUE

        # --- Case B: Only PostalCode provided ---
        # 1) PostalCode must exist for the customer context
        IF NOT ExistsPostalCode(AccountNumber, sp.PostalCode):                  # from Address Directory
            results.APPEND(Result(sp, status="ESCALATE", reason="PostalCodeNotFound"))
            CONTINUE

        # 2) PostalCode must have a valid classification (LARGE_RECIPIENT or CAMPAIGN)
        cls = GetClassification(sp.PostalCode)                                   # from Address Directory
        IF cls IN VALID_CLASSIFICATIONS:
            results.APPEND(Result(sp, status="VALID"))
        ELSE:
            results.APPEND(Result(sp, status="ESCALATE", reason="InvalidClassification"))

    RETURN results


# -----------------------------
# Helper types (for clarity)
# -----------------------------
TYPE ServicePoint:
    Enabled?: boolean
    PostalCode: string                 # maps to ServicePoint.n.PostalCode
    Identifier?: string                # maps to ServicePoint.n.Identifier
    Type?: string                      # maps to ServicePoint.n.Type
    City?: string                      # maps to ServicePoint.n.City

TYPE Result:
    item: ServicePoint
    status: "VALID" | "ESCALATE"
    reason?: string

# -----------------------------
# External validation contracts
# -----------------------------
FUNCTION ExistsCombination(AccountNumber, PostalCode, Identifier) -> boolean
FUNCTION ExistsPostalCode(AccountNumber, PostalCode) -> boolean
FUNCTION GetClassification(PostalCode) -> string