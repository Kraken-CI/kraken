import { NgModule } from '@angular/core';
import { Routes, RouterModule } from '@angular/router';

//import { AuthGuard } from './auth.guard';
import { MainPageComponent } from './main-page/main-page.component';
import { BranchResultsComponent } from './branch-results/branch-results.component';
import { RunResultsComponent } from './run-results/run-results.component';
import { TestCaseResultComponent } from './test-case-result/test-case-result.component';

const routes: Routes = [
    {
        path: '',
        component: MainPageComponent,
        pathMatch: 'full',
        //canActivate: [AuthGuard],
    },
    // {
    //     path: 'login',
    //     component: LoginScreenComponent
    // },
    {
        path: 'branches/:id',
        component: BranchResultsComponent
    },
    {
        path: 'runs/:id',
        component: RunResultsComponent
    },
    {
        path: 'test_case_results/:id',
        component: TestCaseResultComponent
    },


    // otherwise redirect to home
    { path: '**', redirectTo: '' }
];


@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
})
export class AppRoutingModule { }
