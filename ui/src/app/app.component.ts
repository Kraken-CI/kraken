import { Component } from '@angular/core';

import {PanelMenuModule} from 'primeng/panelmenu';
import {MenuModule} from 'primeng/menu';
import {MenuItem} from 'primeng/api';
import {SplitButtonModule} from 'primeng/splitbutton';
import {MultiSelectModule} from 'primeng/multiselect';


@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.sass']
})
export class AppComponent {
    title = 'Kraken';
    logoClass = "logo1";

    items: MenuItem[];
    sItems: MenuItem[];

    constructor() {
        this.logoClass = 'logo' + (Math.floor(Math.random() * 9) + 1);
    }

    ngOnInit() {
        this.items = [{
            label: 'Dashboard',
            icon: 'pi pi-pw pi-home',
            items: [{
                label: 'New',
                icon: 'pi pi-fw pi-plus',
                items: [
                    {label: 'User', icon: 'pi pi-fw pi-user-plus'},
                    {label: 'Filter', icon: 'pi pi-fw pi-filter'}
                ]
            }, {
                label: 'Open', icon: 'pi pi-fw pi-external-link'
            }, {
                separator: true
            }, {
                label: 'Quit', icon: 'pi pi-fw pi-times'
            }, {
                label: 'Edit',
                icon: 'pi pi-fw pi-pencil',
            }]
        }];

        this.sItems = [
            {label: 'Update', icon: 'pi pi-refresh', command: () => {
                //this.update();
            }},
            {label: 'Delete', icon: 'pi pi-times', command: () => {
                //this.delete();
            }},
            {label: 'Angular.io', icon: 'pi pi-info', url: 'http://angular.io'},
            {label: 'Setup', icon: 'pi pi-cog', routerLink: ['/setup']}
        ];
    }
}
