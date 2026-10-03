import { expect, test, type Page } from "@playwright/test";

test("cash income and linked Tax corrections remain exact with safe parent deletion", async ({
  page,
}, testInfo) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  const suffix = await createContext(page);
  await page
    .getByRole("button", { name: "Record transaction", exact: true })
    .click();
  let dialog = page.getByRole("dialog");
  await dialog.getByLabel("Transaction type").selectOption("DIVIDEND");
  await expect(dialog).toContainText("If you only know the net amount");
  await dialog
    .getByLabel("Search or create Instrument")
    .fill(`Income ${suffix}`);
  await dialog.getByRole("button", { name: /^Create Instrument/ }).click();
  await expect(
    dialog.getByLabel("Instrument", { exact: true }),
  ).not.toHaveValue("");
  await dialog.getByLabel("Effective date").fill("2020-01-01");
  await dialog.getByLabel("Currency", { exact: true }).fill("USD");
  await dialog.getByLabel("Gross amount").fill("100");
  await page.screenshot({
    path: testInfo.outputPath("income-dialog.png"),
    fullPage: true,
  });
  await dialog
    .getByRole("button", { name: "Record transaction", exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  await page
    .getByRole("button", { name: "Record transaction", exact: true })
    .click();
  dialog = page.getByRole("dialog");
  await dialog.getByLabel("Transaction type").selectOption("TAX");
  await dialog.getByLabel("Effective date").fill("2020-01-01");
  await dialog.getByLabel("Currency", { exact: true }).fill("USD");
  await dialog.getByLabel("Cash amount").fill("13");
  await dialog
    .getByLabel("Search related transactions")
    .fill(`Income ${suffix}`);
  const picker = dialog.getByLabel("Related transaction (optional)");
  const parentLabel = (await picker.locator("option").allTextContents()).find(
    (text) => text.startsWith("Dividend ·"),
  )!;
  await picker.selectOption({ label: parentLabel });
  await expect(dialog.getByLabel("Instrument (optional)")).toHaveValue("");
  await dialog
    .getByRole("button", { name: "Record transaction", exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  await page.getByRole("tab", { name: "Money", exact: true }).click();
  await page.getByLabel("As of date").fill("2020-01-01");
  const money = page.locator(".money-currency");
  await expect(money.locator(".money-balance")).toHaveText("87 USD");
  await expect(
    money.locator("dl div").filter({ hasText: "Gross dividend income" }),
  ).toContainText("100 USD");
  await expect(
    money.locator("dl div").filter({ hasText: "Gross investment income" }),
  ).toContainText("100 USD");
  await expect(
    money.locator("dl div").filter({ hasText: "Taxes paid or withheld" }),
  ).toContainText("13 USD");
  await page.screenshot({
    path: testInfo.outputPath("money.png"),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("tab", { name: "History", exact: true }).click();
  const rows = page.locator(
    ".history-table tbody tr:visible, .history-mobile article:visible",
  );
  const tax = rows.filter({ hasText: "Tax" });
  const dividend = rows
    .filter({ hasText: "Dividend" })
    .filter({ hasNotText: "Tax" });
  await tax.getByRole("button", { name: "Edit", exact: true }).click();
  dialog = page.getByRole("dialog");
  await dialog.getByLabel("Related transaction (optional)").selectOption("");
  await dialog.getByLabel("Cash amount").fill("10");
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await expect(dialog).toHaveCount(0);
  await page.getByRole("tab", { name: "Money", exact: true }).click();
  await expect(page.getByLabel("As of date")).toHaveValue("2020-01-01");
  await expect(money.locator(".money-balance")).toHaveText("90 USD");
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await tax.getByRole("button", { name: "Edit", exact: true }).click();
  dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("Related transaction (optional)")
    .selectOption({ label: parentLabel });
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await expect(dialog).toHaveCount(0);
  await dividend.getByRole("button", { name: "Delete", exact: true }).click();
  dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Delete permanently" }).click();
  await expect(dialog.getByRole("alert")).toContainText("Nothing was removed");
  await expect(dialog.getByRole("alert")).toContainText(
    "Fee or Tax transaction is linked",
  );
  await dialog.getByRole("button", { name: "Close dialog" }).click();
  await expect(dividend).toHaveCount(1);
  await tax.getByRole("button", { name: "Edit", exact: true }).click();
  dialog = page.getByRole("dialog");
  await dialog.getByLabel("Related transaction (optional)").selectOption("");
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await expect(dialog).toHaveCount(0);
  await dividend.getByRole("button", { name: "Delete", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Delete permanently" })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("tab", { name: "Money", exact: true }).click();
  await expect(money.locator(".money-balance")).toHaveText("−10 USD");
  await page.getByLabel("Account", { exact: true }).selectOption("summary");
  await page.getByRole("tab", { name: "Money", exact: true }).click();
  await expect(money.locator(".money-balance")).toHaveText("−10 USD");
  expect(browserErrors).toEqual([]);
  await expect(
    page.locator("[data-nextjs-dialog], .vite-error-overlay"),
  ).toHaveCount(0);
});

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
  await expect(page.getByRole("tabpanel")).toContainText("Deposit");
  await expect(page.getByRole("tabpanel")).toContainText("Buy");
  await expect(page.getByRole("tabpanel")).toContainText("12.00000000");
  await page.getByRole("tab", { name: "Holdings", exact: true }).click();
  await expect(page.getByRole("table")).toContainText(`Fund ${suffix}`);
  const holding = page.getByRole("row").filter({ hasText: `Fund ${suffix}` });
  await expect(holding.getByRole("cell").nth(1)).toHaveText("2.000000000000");
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

test("corrects and deletes consumed acquisitions through History", async ({
  page,
}) => {
  const suffix = await createContext(page);
  const instrument = `Correctable ${suffix}`;
  await record(page, "Buy", "12", instrument, "2");
  await record(page, "Sell", "9", instrument);
  await page.getByRole("tab", { name: "Realised result", exact: true }).click();
  await expect(page.getByText("3 USD", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  const buy = page
    .locator(".history-table tbody tr:visible, .history-mobile article:visible")
    .filter({ hasText: "Buy" });
  await buy.getByRole("button", { name: "Edit", exact: true }).click();
  let dialog = page.getByRole("dialog");
  await expect(dialog.getByLabel("Cash amount")).toHaveValue("12.00000000");
  await dialog.getByLabel("Cash amount").fill("10");
  await dialog.getByLabel("Quantity", { exact: true }).fill("4");
  await dialog.getByRole("button", { name: "Save changes" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(buy).toContainText("4.000000000000");
  await page.getByRole("tab", { name: "Holdings", exact: true }).click();
  await expect(page.getByRole("table")).toContainText("3.000000000000");
  await page.getByRole("tab", { name: "Realised result", exact: true }).click();
  await expect(page.getByText("6.5 USD", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await buy.getByRole("button", { name: "Delete", exact: true }).click();
  dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("There is no undo");
  await dialog.getByRole("button", { name: "Close dialog" }).click();
  await expect(buy).toBeVisible();
  await buy.getByRole("button", { name: "Delete", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Delete permanently" })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(buy).toHaveCount(0);
  await page.getByRole("tab", { name: "Realised result", exact: true }).click();
  await expect(
    page.getByText("Missing acquisition basis", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Account", { exact: true }).selectOption("summary");
  await page.getByRole("tab", { name: "Realised result", exact: true }).click();
  await expect(
    page.getByText("Missing acquisition basis", { exact: true }),
  ).toBeVisible();
});
