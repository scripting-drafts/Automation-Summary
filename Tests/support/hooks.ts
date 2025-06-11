import { After, Status } from '@cucumber/cucumber';
import { CustomWorld } from './world';
import fs from 'fs';
import path from 'path';

After(async function (this: CustomWorld, scenario) {
  if (scenario.result?.status === Status.FAILED) {
    const screenshot = await this.page.screenshot({ path: `screenshots/${scenario.pickle.name}.png` });
    this.attach(screenshot, 'image/png');
  }

  await this.close();
});