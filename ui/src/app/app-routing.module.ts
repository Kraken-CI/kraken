import { NgModule } from '@angular/core';
import { Routes, RouterModule } from '@angular/router';

//import { AuthGuard } from './auth.guard';
import { BranchResultsComponent } from './branch-results/branch-results.component';

const routes: Routes = [
    {
        path: '',
        //component: BranchResultsComponent,
        redirectTo: 'branches/1',
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


    // otherwise redirect to home
    { path: '**', redirectTo: 'branches/1' }
];


@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
})
export class AppRoutingModule { }
