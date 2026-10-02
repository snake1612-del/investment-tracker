import { expect, test, type Page } from "@playwright/test";

async function createContext(page: Page) {
  const suffix = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  await page.goto("/");
  await page
    .getByRole("button", { name: "Create Portfolio", exact: true })
    .click();
  let dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("Name", { exact: true })
    .fill(`Browser Portfolio ${suffix}`);
  await dialog.getByLabel("Base currency").fill("usd");
  await dialog
    .getByRole("button", { name: "Create Portfolio", exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  await page
    .getByRole("button", { name: "Create Account", exact: true })
    .click();
  dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("Name", { exact: true })
    .fill(`Browser Account ${suffix}`);
  await dialog
    .getByRole("button", { name: "Create Account", exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  await expect(
    page.getByRole("heading", {
      name: `Browser Account ${suffix}`,
      exact: true,
    }),
  ).toBeVisible();
  return suffix;
}

async function record(
  page: Page,
  type: "Deposit" | "Buy" | "Sell",
  amount: string,
  instrument?: string,
  quantity = "1",
  currency = "USD",
) {
  await page
    .getByRole("button", { name: "Record transaction", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Transaction type").selectOption({ label: type });
  await dialog
    .getByLabel("Effective date")
    .fill(type === "Sell" ? "2026-02-02" : "2026-02-01");
  await dialog.getByLabel("Currency", { exact: true }).fill(currency);
  await dialog.getByLabel("Cash amount").fill(amount);
  if (type !== "Deposit") {
    if (type === "Buy") {
      await dialog.getByLabel("Search or create Instrument").fill(instrument!);
      await dialog.getByRole("button", { name: /^Create Instrument/ }).click();
      await expect(
        dialog.getByLabel("Instrument", { exact: true }),
      ).not.toHaveValue("");
    } else {
      const label = await dialog
        .getByLabel("Instrument", { exact: true })
        .locator("option")
        .allTextContents();
      await dialog.getByLabel("Instrument", { exact: true }).selectOption({
        label: label.find((l) => l.startsWith(`${instrument} ·`))!,
      });
    }
    await dialog.getByLabel("Quantity", { exact: true }).fill(quantity);
    await dialog.getByLabel("Price", { exact: true }).fill("5");
  }
  await dialog
    .getByRole("button", { name: "Record transaction", exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  await expect(
    page.getByRole("status").filter({ hasText: "Transaction recorded." }),
  ).toBeVisible();
}

test("complete manual journal journey without API or manual IDs", async ({
  page,
}) => {
  const suffix = await createContext(page);
  await record(page, "Deposit", "1000");
  await record(page, "Buy", "12", `Fund ${suffix}`, "2");
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await expect(page.getByRole("tabpanel")).toContainText("DEPOSIT");
  await expect(page.getByRole("tabpanel")).toContainText("BUY");
  await expect(page.getByRole("tabpanel")).toContainText("12.00000000");
  await page.getByRole("tab", { name: "Holdings", exact: true }).click();
  await expect(page.getByRole("table")).toContainText(`Fund ${suffix}`);
  await expect(page.getByRole("table")).toContainText("2");
  await record(page, "Sell", "9", `Fund ${suffix}`);
  await page.getByRole("tab", { name: "Realised result", exact: true }).click();
  await expect(page.getByText("3 USD", { exact: true })).toBeVisible();
  await expect(page.getByText("Gross", { exact: true })).toBeVisible();
  await expect(page.getByText("Resolved", { exact: true })).toBeVisible();
  await page.getByLabel("Account", { exact: true }).selectOption("summary");
  await expect(
    page.getByRole("button", { name: "Record transaction", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("tab", { name: "History", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("tab", { name: "Realised result", exact: true }).click();
  await expect(page.getByText("3 USD", { exact: true })).toBeVisible();
});

test("oversell remains recordable and displays incomplete result", async ({
  page,
}) => {
  const suffix = await createContext(page);
  await record(page, "Buy", "6", `Incomplete ${suffix}`);
  await record(page, "Sell", "20", `Incomplete ${suffix}`, "2", "EUR");
  await page.getByRole("tab", { name: "Realised result", exact: true }).click();
  await expect(page.getByText("Incomplete", { exact: true })).toBeVisible();
  await expect(
    page.getByText("Currency mismatch", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Missing acquisition basis", { exact: true }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "Holdings", exact: true }).click();
  await expect(page.getByRole("table")).toContainText("Negative quantity");
});
