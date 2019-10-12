import { BrowserModule } from '@angular/platform-browser';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';
import { NgModule } from '@angular/core';
import { HttpClientModule } from '@angular/common/http';

import {PanelMenuModule} from 'primeng/panelmenu';
import {MenuModule} from 'primeng/menu';
import {SplitButtonModule} from 'primeng/splitbutton';
import {DropdownModule} from 'primeng/dropdown';
import {MultiSelectModule} from 'primeng/multiselect';
import {TableModule} from 'primeng/table';

import { ConfigService } from './config.service';
import { BackendService } from './backend.service'

import { ApiModule, BASE_PATH, Configuration } from './backend';
import { AppRoutingModule } from './app-routing.module';
import { AppComponent } from './app.component';
import { BranchResultsComponent } from './branch-results/branch-results.component';
import { RunResultsComponent } from './run-results/run-results.component';

export function cfgFactory() {
    return new Configuration();
}

@NgModule({
    declarations: [
        AppComponent,
        BranchResultsComponent,
        RunResultsComponent
    ],
    imports: [
        BrowserModule,
        BrowserAnimationsModule,
        HttpClientModule,
        ApiModule.forRoot(cfgFactory),
        AppRoutingModule,

        PanelMenuModule,
        MenuModule,
        SplitButtonModule,
        DropdownModule,
        MultiSelectModule,
        TableModule,
    ],
    providers: [ConfigService, BackendService, { provide: BASE_PATH, useValue: 'http://localhost:5000/api' }],
    bootstrap: [AppComponent]
})
export class AppModule { }
