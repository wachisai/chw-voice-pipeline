/**
 * Google Apps Script web app that appends a posted referral to a spreadsheet.
 *
 * Deploy: Extensions > Apps Script from the target sheet, paste this in,
 * Deploy > New deployment > Web app, execute as yourself, access set to
 * "Anyone". Put the resulting /exec URL in SHEETS_WEBHOOK_URL.
 *
 * Deliberately thin. The schema lives in src/schema.py so there is one owner
 * for the column order. This script only writes what it is given, and writes
 * the header once.
 *
 * Note on access: "Anyone" means anyone with the URL can append rows. For a
 * live deployment carrying real referrals, put a shared secret in the payload
 * and check it here, or front the script with an authenticated endpoint.
 */

function doPost(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];
  var payload = JSON.parse(e.postData.contents);

  if (sheet.getLastRow() === 0 && payload.header) {
    sheet.appendRow(payload.header);
    sheet.setFrozenRows(1);
  }
  sheet.appendRow(payload.row);

  return ContentService
    .createTextOutput(JSON.stringify({ ok: true, row: sheet.getLastRow() }))
    .setMimeType(ContentService.MimeType.JSON);
}
