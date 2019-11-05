import { BrowserModule } from '@angular/platform-browser';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';
import { NgModule } from '@angular/core';
import { HttpClientModule } from '@angular/common/http';
import { FormsModule } from '@angular/forms';

import { CodemirrorModule } from '@ctrl/ngx-codemirror';

import {PanelMenuModule} from 'primeng/panelmenu';
import {MenuModule} from 'primeng/menu';
import {SplitButtonModule} from 'primeng/splitbutton';
import {DropdownModule} from 'primeng/dropdown';
import {MultiSelectModule} from 'primeng/multiselect';
import {TableModule} from 'primeng/table';
import {PanelModule} from 'primeng/panel';
import {TreeModule} from 'primeng/tree';
import {ToastModule} from 'primeng/toast';
import {MessageService} from 'primeng/api';
import {TabViewModule} from 'primeng/tabview';
import {OrganizationChartModule} from 'primeng/organizationchart';
import {ChartModule} from 'primeng/chart';
import {SelectButtonModule} from 'primeng/selectbutton';
import {DialogModule} from 'primeng/dialog';
import {InputTextModule} from 'primeng/inputtext';
import {InputTextareaModule} from 'primeng/inputtextarea';
import {MessageModule} from 'primeng/message';
import {ConfirmDialogModule} from 'primeng/confirmdialog';
import {ConfirmationService} from 'primeng/api';
import {InplaceModule} from 'primeng/inplace';
import {PaginatorModule} from 'primeng/paginator';

import { ApiModule, BASE_PATH, Configuration } from './backend';
import { AppRoutingModule } from './app-routing.module';
import { AppComponent } from './app.component';
import { BranchResultsComponent } from './branch-results/branch-results.component';
import { RunResultsComponent } from './run-results/run-results.component';
import { BreadcrumbsComponent } from './breadcrumbs/breadcrumbs.component';
import { BreadcrumbsService } from './breadcrumbs.service';
import { MainPageComponent } from './main-page/main-page.component';
import { TestCaseResultComponent } from './test-case-result/test-case-result.component';
import { FlowResultsComponent } from './flow-results/flow-results.component';
import { BranchMgmtComponent } from './branch-mgmt/branch-mgmt.component';
import { RunBoxComponent } from './run-box/run-box.component';
import { LocaltimePipe } from './localtime.pipe';

export function cfgFactory() {
    return new Configuration();
}

@NgModule({
    declarations: [
        AppComponent,
        BranchResultsComponent,
        RunResultsComponent,
        BreadcrumbsComponent,
        MainPageComponent,
        TestCaseResultComponent,
        FlowResultsComponent,
        BranchMgmtComponent,
        RunBoxComponent,
        LocaltimePipe
    ],
    imports: [
        BrowserModule,
        BrowserAnimationsModule,
        HttpClientModule,
        ApiModule.forRoot(cfgFactory),
        AppRoutingModule,
        FormsModule,

        CodemirrorModule,

        PanelMenuModule,
        MenuModule,
        SplitButtonModule,
        DropdownModule,
        MultiSelectModule,
        TableModule,
        PanelModule,
        TreeModule,
        ToastModule,
        TabViewModule,
        OrganizationChartModule,
        ChartModule,
        SelectButtonModule,
        DialogModule,
        InputTextModule,
        InputTextareaModule,
        MessageModule,
        ConfirmDialogModule,
        InplaceModule,
        PaginatorModule,
    ],
    providers: [{ provide: BASE_PATH, useValue: 'http://localhost:5000/api' },
                BreadcrumbsService, MessageService, ConfirmationService],
    bootstrap: [AppComponent]
})
export class AppModule { }
