import { BrowserModule, Title } from '@angular/platform-browser'
import { BrowserAnimationsModule } from '@angular/platform-browser/animations'
import { NgModule } from '@angular/core'
import { HttpClientModule } from '@angular/common/http'
import { ReactiveFormsModule, FormsModule } from '@angular/forms'

import { CodemirrorModule } from '@ctrl/ngx-codemirror'

import { PanelMenuModule } from 'primeng/panelmenu'
import { MenuModule } from 'primeng/menu'
import { SplitButtonModule } from 'primeng/splitbutton'
import { DropdownModule } from 'primeng/dropdown'
import { MultiSelectModule } from 'primeng/multiselect'
import { TableModule } from 'primeng/table'
import { PanelModule } from 'primeng/panel'
import { TreeModule } from 'primeng/tree'
import { ToastModule } from 'primeng/toast'
import { MessageService } from 'primeng/api'
import { TabViewModule } from 'primeng/tabview'
import { OrganizationChartModule } from 'primeng/organizationchart'
import { ChartModule } from 'primeng/chart'
import { SelectButtonModule } from 'primeng/selectbutton'
import { DialogModule } from 'primeng/dialog'
import { InputTextModule } from 'primeng/inputtext'
import { InputTextareaModule } from 'primeng/inputtextarea'
import { MessageModule } from 'primeng/message'
import { ConfirmDialogModule } from 'primeng/confirmdialog'
import { ConfirmationService } from 'primeng/api'
import { InplaceModule } from 'primeng/inplace'
import { PaginatorModule } from 'primeng/paginator'
import { TabMenuModule } from 'primeng/tabmenu'
import { CheckboxModule } from 'primeng/checkbox'
import { MenubarModule } from 'primeng/menubar'
import { InputSwitchModule } from 'primeng/inputswitch'
import { SpinnerModule } from 'primeng/spinner'
import { PasswordModule } from 'primeng/password'
import { TooltipModule } from 'primeng/tooltip';

import { ApiModule, BASE_PATH, Configuration } from './backend'
import { AppRoutingModule } from './app-routing.module'
import { AppComponent } from './app.component'
import { BranchResultsComponent } from './branch-results/branch-results.component'
import { RunResultsComponent } from './run-results/run-results.component'
import { BreadcrumbsComponent } from './breadcrumbs/breadcrumbs.component'
import { BreadcrumbsService } from './breadcrumbs.service'
import { MainPageComponent } from './main-page/main-page.component'
import { TestCaseResultComponent } from './test-case-result/test-case-result.component'
import { FlowResultsComponent } from './flow-results/flow-results.component'
import { BranchMgmtComponent } from './branch-mgmt/branch-mgmt.component'
import { RunBoxComponent } from './run-box/run-box.component'
import { LocaltimePipe } from './localtime.pipe'
import { NewFlowComponent } from './new-flow/new-flow.component'
import { NewRunComponent } from './new-run/new-run.component'
import { LogBoxComponent } from './log-box/log-box.component'
import { ProjectSettingsComponent } from './project-settings/project-settings.component'
import { ExecutorsPageComponent } from './executors-page/executors-page.component'
import { DiscoveredPageComponent } from './discovered-page/discovered-page.component'
import { GroupsPageComponent } from './groups-page/groups-page.component';
import { SettingsPageComponent } from './settings-page/settings-page.component'

export function cfgFactory() {
    return new Configuration()
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
        LocaltimePipe,
        NewFlowComponent,
        NewRunComponent,
        LogBoxComponent,
        ProjectSettingsComponent,
        ExecutorsPageComponent,
        DiscoveredPageComponent,
        GroupsPageComponent,
        SettingsPageComponent,
    ],
    imports: [
        BrowserModule,
        BrowserAnimationsModule,
        HttpClientModule,
        ApiModule.forRoot(cfgFactory),
        AppRoutingModule,
        FormsModule,
        ReactiveFormsModule,

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
        TabMenuModule,
        CheckboxModule,
        MenubarModule,
        InputSwitchModule,
        SpinnerModule,
        PasswordModule,
        TooltipModule,
    ],
    providers: [
        Title,
        { provide: BASE_PATH, useValue: '/api' },
        BreadcrumbsService,
        MessageService,
        ConfirmationService,
    ],
    bootstrap: [AppComponent],
})
export class AppModule {}
